from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..core.rate_limiter import limiter, rate_limit_str
from ..database import get_db
from ..models import Agent, AgentSigningKey
from ..schemas.capability import normalize_capabilities
from ..core.avid import validate_avid_format

router = APIRouter()

_ACTIVE_WINDOW = timedelta(minutes=5)


def _verification(agent_avid: Optional[str], has_signing_key: bool, last_heartbeat_at) -> dict:
    avid = agent_avid or ""
    avid_ok = bool(avid) and validate_avid_format(avid)
    now = datetime.utcnow()
    active = bool(last_heartbeat_at and last_heartbeat_at >= (now - _ACTIVE_WINDOW))

    if not avid_ok:
        return {"verified_by_avos": False, "verification_level": "unverified", "active": active}
    if has_signing_key and active:
        return {"verified_by_avos": True, "verification_level": "active", "active": True}
    if has_signing_key:
        return {"verified_by_avos": True, "verification_level": "signed", "active": active}
    return {"verified_by_avos": True, "verification_level": "basic", "active": active}


@router.get("/agents/public")
@limiter.limit(rate_limit_str)
def public_agents(request: Request, db: Session = Depends(get_db)):
    """Return public metadata for agents so developers can discover reliable collaborators."""
    agents = (
        db.query(
            Agent.agent_id,
            Agent.avid,
            Agent.name,
            Agent.reputation_score,
            Agent.total_tasks_executed,
            Agent.capabilities,
            Agent.last_heartbeat_at,
            AgentSigningKey.agent_id.label("has_signing_key"),
        )
        .outerjoin(AgentSigningKey, AgentSigningKey.agent_id == Agent.agent_id)
        .order_by(Agent.reputation_score.desc())
        .all()
    )
    return [
        {
            "agent_id": row.agent_id,
            "avid": row.avid,
            "agent_name": row.name,
            "reputation_score": row.reputation_score,
            "tasks_completed": row.total_tasks_executed,
            "capabilities": normalize_capabilities(row.capabilities),
            "last_heartbeat_at": row.last_heartbeat_at,
            **_verification(row.avid, bool(row.has_signing_key), row.last_heartbeat_at),
        }
        for row in agents
    ]


@router.get("/agents/search")
@limiter.limit(rate_limit_str)
def search_agents(
    request: Request,
    capability: Optional[str] = Query(None, description="Filter agents that advertise the capability"),
    min_reputation: float = Query(0, ge=0, description="Minimum reputation score"),
    db: Session = Depends(get_db),
):
    """Find agents whose capabilities and reputation match the provided filters."""
    query = (
        db.query(
            Agent,
            AgentSigningKey.agent_id.label("has_signing_key"),
        )
        .outerjoin(AgentSigningKey, AgentSigningKey.agent_id == Agent.agent_id)
        .filter(Agent.reputation_score >= min_reputation)
        .order_by(Agent.reputation_score.desc())
        .limit(200)
    )
    rows = query.all()
    agents = [(agent, bool(has_key)) for agent, has_key in rows]
    if capability:
        wanted = capability.strip().lower()
        agents = [
            (agent, has_key)
            for (agent, has_key) in agents
            if any(
                str(item.get("name", "")).lower() == wanted
                for item in normalize_capabilities(agent.capabilities)
                if isinstance(item, dict)
            )
        ]
    agents = agents[:50]
    return [
        {
            "agent_id": agent.agent_id,
            "avid": agent.avid,
            "agent_name": agent.name,
            "reputation_score": agent.reputation_score,
            "tasks_completed": agent.total_tasks_executed,
            "capabilities": normalize_capabilities(agent.capabilities),
            "last_heartbeat_at": agent.last_heartbeat_at,
            **_verification(agent.avid, has_key, agent.last_heartbeat_at),
        }
        for agent, has_key in agents
    ]


@router.get("/agents/verified")
@limiter.limit(rate_limit_str)
def verified_agents(
    request: Request,
    active_only: bool = Query(False, description="Only agents with heartbeat < 5 minutes"),
    min_reputation: float = Query(0, ge=0, description="Minimum reputation score"),
    capability: Optional[str] = Query(None, description="Optional capability filter"),
    db: Session = Depends(get_db),
):
    """Public directory of AVOS-verified agents.

    For MVP, "verified" means:
    - agent has a valid AVID, and
    - agent registered an ECDSA signing public key for A2A verification.
    """
    query = (
        db.query(Agent, AgentSigningKey.agent_id.label("has_signing_key"))
        .join(AgentSigningKey, AgentSigningKey.agent_id == Agent.agent_id)
        .filter(Agent.reputation_score >= min_reputation)
        .order_by(Agent.reputation_score.desc())
        .limit(200)
    )
    rows = query.all()
    agents = []
    for agent, _ in rows:
        if not agent.avid or not validate_avid_format(agent.avid):
            continue
        if active_only:
            now = datetime.utcnow()
            if not (agent.last_heartbeat_at and agent.last_heartbeat_at >= (now - _ACTIVE_WINDOW)):
                continue
        agents.append(agent)

    if capability:
        wanted = capability.strip().lower()
        agents = [
            agent
            for agent in agents
            if any(
                str(item.get("name", "")).lower() == wanted
                for item in normalize_capabilities(agent.capabilities)
                if isinstance(item, dict)
            )
        ]

    agents = agents[:50]
    return [
        {
            "agent_id": agent.agent_id,
            "avid": agent.avid,
            "agent_name": agent.name,
            "reputation_score": agent.reputation_score,
            "tasks_completed": agent.total_tasks_executed,
            "capabilities": normalize_capabilities(agent.capabilities),
            "last_heartbeat_at": agent.last_heartbeat_at,
            **_verification(agent.avid, True, agent.last_heartbeat_at),
        }
        for agent in agents
    ]


@router.get("/agents/identity/{avid}")
@limiter.limit(rate_limit_str)
def public_identity_by_avid(
    request: Request,
    avid: str,
    db: Session = Depends(get_db),
):
    """Public, safe identity lookup by AVID (no owner_id, no keys)."""
    agent = db.query(Agent).filter(Agent.avid == avid).first()
    if not agent:
        raise HTTPException(status_code=404, detail="AVID not found")
    has_key = bool(db.query(AgentSigningKey).filter(AgentSigningKey.agent_id == agent.agent_id).first())
    return {
        "avid": agent.avid,
        "agent_name": agent.name,
        "capabilities": normalize_capabilities(agent.capabilities),
        "reputation_score": agent.reputation_score,
        "tasks_completed": agent.total_tasks_executed,
        "last_heartbeat_at": agent.last_heartbeat_at,
        **_verification(agent.avid, has_key, agent.last_heartbeat_at),
    }
