from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..core.a2a import payload_sha256_hex, verify_a2a_signature
from ..core.events import broker
from ..core.rate_limiter import limiter, rate_limit_str
from ..core.security import get_current_agent
from ..database import get_db
from ..models import A2AMessage, Agent, AgentSigningKey
from ..schemas.a2a import (
    A2AMessageItem,
    A2ASendRequest,
    A2ASendResponse,
    RegisterSigningKeyRequest,
    RegisterSigningKeyResponse,
)

router = APIRouter()
logger = structlog.get_logger()


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
