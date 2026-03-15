from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..core.a2a import (
    canonical_handshake_confirm_bytes,
    canonical_handshake_init_bytes,
    payload_sha256_hex,
    verify_a2a_signature,
)
from ..core.audit_chain import compute_chain_hash
from ..core.events import broker
from ..core.rate_limiter import limiter, rate_limit_str
from ..core.security import get_current_agent
from ..core.signatures import sha256_digest, verify_ecdsa_p256_sha256
from ..database import get_db
from ..models import A2AMessage, A2ASession, Agent, AgentSigningKey
from ..schemas.a2a import (
    A2AMessageItem,
    A2ASendRequest,
    A2ASendResponse,
    RegisterSigningKeyRequest,
    RegisterSigningKeyResponse,
)
from ..schemas.ahp import (
    HandshakeConfirmRequest,
    HandshakeConfirmResponse,
    HandshakeInfoResponse,
    HandshakeInitRequest,
    HandshakeInitResponse,
)

router = APIRouter()
logger = structlog.get_logger()
_HANDSHAKE_TTL = timedelta(minutes=10)


@router.post("/a2a/signing_key", response_model=RegisterSigningKeyResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(rate_limit_str)
def register_signing_key(
    request: Request,
    payload: RegisterSigningKeyRequest,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    """Register an agent signing public key (immutable)."""
    existing = db.query(AgentSigningKey).filter(AgentSigningKey.agent_id == current_agent.agent_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Signing key already registered")
    row = AgentSigningKey(agent_id=current_agent.agent_id, public_key_pem=payload.public_key_pem)
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("a2a.signing_key_registered", agent_id=current_agent.agent_id, avid=current_agent.avid)
    broker.publish(
        "a2a_signing_key_registered",
        {"agent_id": current_agent.agent_id, "avid": current_agent.avid or "", "created_at": row.created_at},
    )
    return RegisterSigningKeyResponse(agent_id=current_agent.agent_id, avid=current_agent.avid or "", created_at=row.created_at)


def _avid_to_agent(db: Session, avid: str) -> Optional[Agent]:
    return db.query(Agent).filter(Agent.avid == avid).first()


@router.post("/a2a/send", response_model=A2ASendResponse)
@limiter.limit(rate_limit_str)
def a2a_send(
    request: Request,
    payload: A2ASendRequest,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    """Send a signed A2A message to another agent by AVID.

    Messages are stored server-side for delivery (polling) and fully auditable.
    """
    if not current_agent.avid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent has no AVID")

    recipient = _avid_to_agent(db, payload.to_avid)
    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient AVID not found")

    signer = db.query(AgentSigningKey).filter(AgentSigningKey.agent_id == current_agent.agent_id).first()
    if not signer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signing key not registered for this agent")

    # Prevent replay / duplicates.
    exists = (
        db.query(A2AMessage)
        .filter(A2AMessage.from_agent_id == current_agent.agent_id)
        .filter(A2AMessage.message_id == payload.message_id)
        .first()
    )
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate message_id for sender")

    verified = verify_a2a_signature(
        signer.public_key_pem,
        from_avid=current_agent.avid,
        to_avid=payload.to_avid,
        message_id=payload.message_id,
        sent_at=payload.sent_at,
        message_type=payload.message_type,
        payload=payload.payload,
        signature=payload.signature,
    )
    if not verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid A2A signature")

    prev = (
        db.query(A2AMessage.entry_hash)
        .filter(A2AMessage.from_agent_id == current_agent.agent_id)
        .order_by(A2AMessage.id.desc())
        .limit(1)
        .scalar()
    )
    entry_hash = compute_chain_hash(
        prev_hash=prev,
        namespace="a2a_message",
        fields={
            "from_avid": current_agent.avid,
            "to_avid": payload.to_avid,
            "message_id": payload.message_id,
            "sent_at": payload.sent_at.isoformat() + "Z",
            "message_type": payload.message_type,
            "payload_sha256": payload_sha256_hex(payload.payload),
            "signature": payload.signature,
        },
    )
    msg = A2AMessage(
        from_agent_id=current_agent.agent_id,
        to_agent_id=recipient.agent_id,
        from_avid=current_agent.avid,
        to_avid=payload.to_avid,
        message_id=payload.message_id,
        message_type=payload.message_type,
        sent_at=payload.sent_at,
        payload=json.dumps(payload.payload, separators=(",", ":"), default=str),
        payload_sha256=payload_sha256_hex(payload.payload),
        signature=payload.signature,
        verified=True,
        created_at=datetime.utcnow(),
        prev_hash=prev,
        entry_hash=entry_hash,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    logger.info(
        "a2a.message_sent",
        from_avid=current_agent.avid,
        to_avid=payload.to_avid,
        message_type=payload.message_type,
        message_id=payload.message_id,
    )
    broker.publish(
        "a2a_message_sent",
        {
            "from_avid": current_agent.avid,
            "to_avid": payload.to_avid,
            "message_type": payload.message_type,
            "message_id": payload.message_id,
            "stored_id": msg.id,
        },
    )

    return A2ASendResponse(status="queued", stored_id=msg.id, verified=True)


@router.post("/a2a/handshake/init", response_model=HandshakeInitResponse)
@limiter.limit(rate_limit_str)
def handshake_init(
    request: Request,
    payload: HandshakeInitRequest,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    """Apex Handshake Protocol (AHP) – init step.

    The initiator signs a canonical init payload; AVOS issues a responder nonce and session_id.
    """
    if not current_agent.avid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent has no AVID")

    recipient = _avid_to_agent(db, payload.to_avid)
    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient AVID not found")

    signer = db.query(AgentSigningKey).filter(AgentSigningKey.agent_id == current_agent.agent_id).first()
    if not signer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signing key not registered for this agent")

    # Verify initiator signature.
    digest = sha256_digest(
        canonical_handshake_init_bytes(
            from_avid=current_agent.avid,
            to_avid=payload.to_avid,
            message_id=payload.message_id,
            sent_at=payload.sent_at,
            constraints=payload.constraints or {},
        )
    )
    if not verify_ecdsa_p256_sha256(signer.public_key_pem, digest, payload.signature):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid handshake init signature")

    session_id = secrets.token_urlsafe(24)
    initiator_nonce = secrets.token_urlsafe(24)
    responder_nonce = secrets.token_urlsafe(24)
    now = datetime.utcnow()
    expires_at = now + _HANDSHAKE_TTL

    row = A2ASession(
        session_id=session_id,
        initiator_agent_id=current_agent.agent_id,
        responder_agent_id=recipient.agent_id,
        initiator_avid=current_agent.avid,
        responder_avid=payload.to_avid,
        initiator_nonce=initiator_nonce,
        responder_nonce=responder_nonce,
        constraints=payload.constraints or {},
        status="pending",
        created_at=now,
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    broker.publish(
        "a2a_handshake_init",
        {"session_id": row.session_id, "from_avid": row.initiator_avid, "to_avid": row.responder_avid, "expires_at": row.expires_at},
    )
    return HandshakeInitResponse(
        session_id=row.session_id,
        from_avid=row.initiator_avid,
        to_avid=row.responder_avid,
        responder_nonce=row.responder_nonce,
        expires_at=row.expires_at,
        status=row.status,
    )


@router.post("/a2a/handshake/confirm", response_model=HandshakeConfirmResponse)
@limiter.limit(rate_limit_str)
def handshake_confirm(
    request: Request,
    payload: HandshakeConfirmRequest,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    """AHP confirm step (responder signs to activate the session)."""
    if not current_agent.avid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent has no AVID")

    session = db.query(A2ASession).filter(A2ASession.session_id == payload.session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.responder_agent_id != current_agent.agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the session responder")
    if session.status != "pending":
        return HandshakeConfirmResponse(session_id=session.session_id, status=session.status, confirmed_at=session.confirmed_at)
    if datetime.utcnow() > session.expires_at:
        session.status = "expired"
        db.commit()
        return HandshakeConfirmResponse(session_id=session.session_id, status="expired", confirmed_at=None)

    signer = db.query(AgentSigningKey).filter(AgentSigningKey.agent_id == current_agent.agent_id).first()
    if not signer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signing key not registered for this agent")

    digest = sha256_digest(
        canonical_handshake_confirm_bytes(
            session_id=session.session_id,
            from_avid=session.initiator_avid,
            to_avid=session.responder_avid,
            initiator_nonce=session.initiator_nonce,
            responder_nonce=session.responder_nonce,
        )
    )
    if not verify_ecdsa_p256_sha256(signer.public_key_pem, digest, payload.signature):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid handshake confirm signature")

    session.status = "active"
    session.confirmed_at = datetime.utcnow()
    db.commit()
    broker.publish(
        "a2a_handshake_active",
        {"session_id": session.session_id, "from_avid": session.initiator_avid, "to_avid": session.responder_avid},
    )
    return HandshakeConfirmResponse(session_id=session.session_id, status="active", confirmed_at=session.confirmed_at)


@router.get("/a2a/handshake/{session_id}", response_model=HandshakeInfoResponse)
@limiter.limit(rate_limit_str)
def handshake_info(
    request: Request,
    session_id: str,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    """Fetch handshake session details for signing (responder only)."""
    session = db.query(A2ASession).filter(A2ASession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.responder_agent_id != current_agent.agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the session responder")
    return HandshakeInfoResponse(
        session_id=session.session_id,
        from_avid=session.initiator_avid,
        to_avid=session.responder_avid,
        initiator_nonce=session.initiator_nonce,
        responder_nonce=session.responder_nonce,
        status=session.status,
        expires_at=session.expires_at,
    )


@router.get("/a2a/inbox", response_model=list[A2AMessageItem])
@limiter.limit(rate_limit_str)
def a2a_inbox(
    request: Request,
    limit: int = 50,
    mark_delivered: bool = True,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    """Fetch inbound A2A messages for the current agent."""
    rows = (
        db.query(A2AMessage)
        .filter(A2AMessage.to_agent_id == current_agent.agent_id)
        .filter(A2AMessage.delivered_at == None)  # noqa: E711
        .order_by(A2AMessage.created_at.asc())
        .limit(limit)
        .all()
    )
    now = datetime.utcnow()
    if mark_delivered and rows:
        for row in rows:
            row.delivered_at = now
        db.commit()

    items: list[A2AMessageItem] = []
    for row in rows:
        try:
            payload_dict: Dict[str, Any] = json.loads(row.payload)
        except Exception:
            payload_dict = {}
        items.append(
            A2AMessageItem(
                id=row.id,
                from_avid=row.from_avid,
                to_avid=row.to_avid,
                message_id=row.message_id,
                message_type=row.message_type,
                sent_at=row.sent_at,
                payload=payload_dict,
                payload_sha256=row.payload_sha256,
                verified=bool(row.verified),
                created_at=row.created_at,
                delivered_at=row.delivered_at,
            )
        )
    return items
