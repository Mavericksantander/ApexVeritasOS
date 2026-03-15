from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.avid import validate_avid_format
from ..core.rate_limiter import limiter, rate_limit_str
from ..core.security import get_current_agent
from ..core.signatures import canonical_json_bytes, sha256_digest, verify_ecdsa_p256_sha256
from ..database import get_db
from ..models import Agent, AgentPeerAttestation, AgentSigningKey
from ..core.peer_attestations import aggregate_peer_adjustments

router = APIRouter()

_DIMENSIONS = {"competence", "safety", "availability", "transparency"}


class PeerAttestRequest(BaseModel):
    """A peer vouch/attestation about another agent.

    The attester must be authenticated (JWT) and have a registered signing key (ECDSA P-256 public key).
    The signature is verified against a canonical JSON payload.
    """

    target_avid: str = Field(..., min_length=8, max_length=80)
    dimension: Literal["competence", "safety", "availability", "transparency"]
    score_delta: float = Field(..., ge=-0.25, le=0.25)
    evidence_task_id: Optional[int] = Field(default=None, ge=1)
    evidence_session_id: Optional[str] = Field(default=None, max_length=128)
    reason: Optional[str] = Field(default=None, max_length=512)
    attested_at: datetime
    signature: str = Field(..., min_length=16, max_length=20000)


class PeerAttestResponse(BaseModel):
    id: int
    from_avid: str
    target_avid: str
    dimension: str
    score_delta: float
    evidence_task_id: Optional[int] = None
    evidence_session_id: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime
    revoked: bool


def _attestation_payload_dict(from_avid: str, payload: PeerAttestRequest) -> Dict[str, Any]:
    return {
        "from_avid": from_avid,
        "target_avid": payload.target_avid,
        "dimension": payload.dimension,
        "score_delta": float(payload.score_delta),
        "evidence_task_id": payload.evidence_task_id,
        "evidence_session_id": payload.evidence_session_id,
        "reason": payload.reason or "",
        "attested_at": payload.attested_at.isoformat() + "Z",
    }


@router.post("/trust/attest", response_model=PeerAttestResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(rate_limit_str)
def attest(
    request: Request,
    payload: PeerAttestRequest,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    """Create a signed peer attestation about a target agent (by AVID).

    Anti-spam MVP guardrails:
    - attester must have AVID + signing key registered
    - attester must have at least 3 successful tasks
    - attested_at must be within +/- 5 minutes of server time
    - dedupe by (from_agent_id, target_avid, dimension, evidence_task_id/evidence_session_id)
    """
    if not current_agent.avid or not validate_avid_format(current_agent.avid):
        raise HTTPException(status_code=400, detail="Attester must have a valid AVID")
    if not validate_avid_format(payload.target_avid):
        raise HTTPException(status_code=400, detail="Invalid target AVID format")
    if payload.dimension not in _DIMENSIONS:
        raise HTTPException(status_code=400, detail="Invalid dimension")

    # Require basic competence before the attester influences others.
    if int(getattr(current_agent, "tasks_success", 0) or 0) < 3:
        raise HTTPException(status_code=403, detail="Attester needs >= 3 successful tasks")

    now = datetime.utcnow()
    if abs((now - payload.attested_at).total_seconds()) > 300:
        raise HTTPException(status_code=400, detail="attested_at out of acceptable window")

    key = db.query(AgentSigningKey).filter(AgentSigningKey.agent_id == current_agent.agent_id).first()
    if not key:
        raise HTTPException(status_code=400, detail="Attester signing key not registered")

    signed = _attestation_payload_dict(current_agent.avid, payload)
    digest = sha256_digest(canonical_json_bytes(signed))
    if not verify_ecdsa_p256_sha256(key.public_key_pem, digest, payload.signature):
        raise HTTPException(status_code=403, detail="Invalid attestation signature")

    # Dedupe: evidence_task_id preferred, else evidence_session_id, else "none".
    existing = (
        db.query(AgentPeerAttestation)
        .filter(AgentPeerAttestation.from_agent_id == current_agent.agent_id)
        .filter(AgentPeerAttestation.target_avid == payload.target_avid)
        .filter(AgentPeerAttestation.dimension == payload.dimension)
        .filter(AgentPeerAttestation.evidence_task_id == payload.evidence_task_id)
        .filter(AgentPeerAttestation.evidence_session_id == payload.evidence_session_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Duplicate attestation")

    row = AgentPeerAttestation(
        from_agent_id=current_agent.agent_id,
        from_avid=current_agent.avid,
        target_avid=payload.target_avid,
        dimension=payload.dimension,
        score_delta=float(payload.score_delta),
        evidence_task_id=payload.evidence_task_id,
        evidence_session_id=payload.evidence_session_id,
        reason=payload.reason,
        signature=payload.signature,
        revoked=False,
        created_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return PeerAttestResponse(
        id=row.id,
        from_avid=row.from_avid,
        target_avid=row.target_avid,
        dimension=row.dimension,
        score_delta=float(row.score_delta),
        evidence_task_id=row.evidence_task_id,
        evidence_session_id=row.evidence_session_id,
        reason=row.reason,
        created_at=row.created_at,
        revoked=bool(row.revoked),
    )


@router.get("/trust/attestations/{avid}")
@limiter.limit(rate_limit_str)
def list_attestations(
    request: Request,
    avid: str,
    since_days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Public: list recent peer attestations for a target AVID (safe fields only)."""
    if not validate_avid_format(avid):
        raise HTTPException(status_code=400, detail="Invalid AVID format")
    since = datetime.utcnow() - timedelta(days=int(since_days))
    rows = (
        db.query(AgentPeerAttestation)
        .filter(AgentPeerAttestation.target_avid == avid)
        .filter(AgentPeerAttestation.created_at >= since)
        .order_by(AgentPeerAttestation.created_at.desc())
        .limit(int(limit))
        .all()
    )
    return [
        {
            "id": r.id,
            "from_avid": r.from_avid,
            "target_avid": r.target_avid,
            "dimension": r.dimension,
            "score_delta": float(r.score_delta),
            "evidence_task_id": r.evidence_task_id,
            "evidence_session_id": r.evidence_session_id,
            "reason": r.reason,
            "created_at": r.created_at,
            "revoked": bool(r.revoked),
        }
        for r in rows
    ]
