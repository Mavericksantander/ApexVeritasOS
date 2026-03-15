from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..core.avid import validate_avid_format
from ..core.rate_limiter import limiter, rate_limit_str
from ..core.reputation_metrics import effective_reputation, success_rate
from ..core.registry_crypto import verify_attestation_hmac
from ..core.config import settings
from ..database import get_db
from ..models import Agent, AgentAttestation, AgentSigningKey
from ..schemas.capability import normalize_capabilities
from ..schemas.registry import AttestationCreateRequest, AttestationResponse, RegistryAgentItem

router = APIRouter()
logger = structlog.get_logger()

_ACTIVE_WINDOW = timedelta(minutes=5)


def _issuer_keys() -> Dict[str, str]:
    # MVP: allow a JSON-ish string in env, e.g. {"ExampleCorp":"secret"}.
    # pydantic-settings will not parse this automatically in our current settings, so we keep it simple.
    raw = getattr(settings, "REGISTRY_ISSUER_KEYS", None)
    if not raw:
        return {}
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    try:
        import json

        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        return {}
    return {}


def _verification(agent: Agent, has_signing_key: bool) -> dict:
    avid_ok = bool(agent.avid) and validate_avid_format(agent.avid)
    now = datetime.utcnow()
    active = bool(agent.last_heartbeat_at and agent.last_heartbeat_at >= (now - _ACTIVE_WINDOW))
    if not avid_ok:
        return {"verified_by_avos": False, "verification_level": "unverified", "active": active}
    if has_signing_key and active:
        return {"verified_by_avos": True, "verification_level": "active", "active": True}
    if has_signing_key:
        return {"verified_by_avos": True, "verification_level": "signed", "active": active}
    return {"verified_by_avos": True, "verification_level": "basic", "active": active}


@router.get("/registry/agents", response_model=list[RegistryAgentItem])
@limiter.limit(rate_limit_str)
def registry_agents(
    request: Request,
    capability: Optional[str] = Query(None),
    min_reputation: float = Query(0, ge=0),
    active_only: bool = Query(False),
    include_attestations: bool = Query(True),
    db: Session = Depends(get_db),
):
    """Apex Registry: public directory of verified agents.

    This is the "identity network" view. It is safe for unauthenticated discovery.
    """
    query = (
        db.query(Agent, AgentSigningKey.agent_id.label("has_signing_key"))
        .outerjoin(AgentSigningKey, AgentSigningKey.agent_id == Agent.agent_id)
        .filter(Agent.reputation_score >= min_reputation)
        .order_by(Agent.reputation_score.desc())
        .limit(500)
    )
    rows = query.all()
    agents: list[RegistryAgentItem] = []
    now = datetime.utcnow()
    for agent, has_key in rows:
        if not agent.avid or not validate_avid_format(agent.avid):
            continue
        if active_only and not (agent.last_heartbeat_at and agent.last_heartbeat_at >= (now - _ACTIVE_WINDOW)):
            continue
        caps = normalize_capabilities(agent.capabilities)
        if capability:
            wanted = capability.strip().lower()
            if not any(str(item.get("name", "")).lower() == wanted for item in caps if isinstance(item, dict)):
                continue

        attestations: list[AttestationResponse] = []
        if include_attestations:
            rows_att = (
                db.query(AgentAttestation)
                .filter(AgentAttestation.agent_id == agent.agent_id)
                .order_by(AgentAttestation.created_at.desc())
                .limit(20)
                .all()
            )
            attestations = [
                AttestationResponse(
                    id=a.id,
                    avid=a.avid,
                    issuer=a.issuer,
                    claim_type=a.claim_type,
                    claim_value=a.claim_value or {},
                    verified=bool(a.verified),
                    created_at=a.created_at,
                )
                for a in rows_att
            ]

        ver = _verification(agent, bool(has_key))
        agents.append(
            RegistryAgentItem(
                avid=agent.avid,
                agent_name=agent.name,
                capabilities=caps,
                reputation_score=float(agent.reputation_score or 0.0),
                reputation_effective=float(
                    effective_reputation(agent.reputation_score or 0.0, last_activity_at=getattr(agent, "last_task_at", None) or agent.registered_at)
                ),
                success_rate=success_rate(getattr(agent, "tasks_success", 0) or 0, getattr(agent, "tasks_failure", 0) or 0),
                trust_vector=getattr(agent, "trust_vector", None) or {},
                trust_updated_at=getattr(agent, "trust_updated_at", None),
                verification_level=ver["verification_level"],
                verified_by_avos=ver["verified_by_avos"],
                active=ver["active"],
                last_heartbeat_at=agent.last_heartbeat_at,
                last_task_at=getattr(agent, "last_task_at", None),
                attestations=attestations,
            )
        )
        if len(agents) >= 200:
            break
    return agents


@router.post("/registry/attestations", response_model=AttestationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(rate_limit_str)
def create_attestation(
    request: Request,
    payload: AttestationCreateRequest,
    db: Session = Depends(get_db),
):
    """Create an issuer attestation for an agent.

    MVP uses HMAC issuer keys configured in `REGISTRY_ISSUER_KEYS`.
    """
    if not validate_avid_format(payload.avid):
        raise HTTPException(status_code=400, detail="Invalid AVID format")
    agent = db.query(Agent).filter(Agent.avid == payload.avid).first()
    if not agent:
        raise HTTPException(status_code=404, detail="AVID not found")

    keys = _issuer_keys()
    secret = keys.get(payload.issuer)
    if not secret:
        raise HTTPException(status_code=401, detail="Unknown issuer")
    if not verify_attestation_hmac(secret, payload.signature, payload.avid, payload.issuer, payload.claim_type, payload.claim_value):
        raise HTTPException(status_code=403, detail="Invalid attestation signature")

    row = AgentAttestation(
        agent_id=agent.agent_id,
        avid=payload.avid,
        issuer=payload.issuer,
        claim_type=payload.claim_type,
        claim_value=payload.claim_value,
        signature=payload.signature,
        verified=True,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("registry.attestation_created", avid=payload.avid, issuer=payload.issuer, claim_type=payload.claim_type)
    return AttestationResponse(
        id=row.id,
        avid=row.avid,
        issuer=row.issuer,
        claim_type=row.claim_type,
        claim_value=row.claim_value or {},
        verified=True,
        created_at=row.created_at,
    )
