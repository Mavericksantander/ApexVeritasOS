from datetime import datetime, timedelta
from uuid import uuid4
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import structlog

from ..core.rate_limiter import limiter, rate_limit_str
from ..core.security import create_access_token, get_current_agent, pwd_context
from ..database import get_db
from ..models import Agent, AgentKey
from ..core.events import broker
from ..schemas.agent import ActiveAgentResponse, AgentIdentityResponse
from ..schemas.capability import CapabilityItem, capability_names, normalize_capabilities
from ..core.avid import generate_avid
from ..core.constitution import constitution_hash
from ..schemas.reputation import AgentReputationResponse, AgentReputationSignals
from ..core.reputation_metrics import effective_reputation, success_rate
from ..core.trust_vector import compute_trust_vector
from ..core.peer_attestations import aggregate_peer_adjustments
from .deps import verify_owner

router = APIRouter()
logger = structlog.get_logger()


class RegisterAgentRequest(BaseModel):
    agent_name: str = Field(..., max_length=64)
    owner_id: str = Field(..., max_length=64)
    capabilities: list[object] = Field(default_factory=list)


class RegisterAgentResponse(BaseModel):
    avid: str
    agent_id: str
    public_key: str
    access_token: str
    token_type: str = "bearer"
    registration_timestamp: datetime


class AgentInfoResponse(BaseModel):
    agent_id: str
    name: str
    reputation_score: float
    registered_capabilities: list[str]
    total_tasks_executed: int
    registered_at: datetime


@router.post("/register_agent", response_model=RegisterAgentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(rate_limit_str)
def register_agent(
    request: Request, payload: RegisterAgentRequest, db: Session = Depends(get_db)
):
    agent_id = str(uuid4())
    public_key_value = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    normalized_caps = normalize_capabilities(payload.capabilities)
    avid = generate_avid(
        public_key_value,
        {
            "agent_name": payload.agent_name,
            "owner_id": payload.owner_id,
            "capabilities": normalized_caps,
        },
        constitution_hash=constitution_hash(),
        created_at=now,
    )
    agent = Agent(
        agent_id=agent_id,
        avid=avid,
        name=payload.agent_name,
        owner_id=payload.owner_id,
        capabilities=normalized_caps,
        public_key=pwd_context.hash(public_key_value),
        registered_at=now,
    )
    db.add(agent)
    db.add(AgentKey(agent_id=agent_id, public_key=public_key_value))
    db.commit()
    db.refresh(agent)
    token = create_access_token(
        {"agent_id": agent.agent_id, "capabilities": capability_names(agent.capabilities), "reputation": agent.reputation_score}
    )
    logger.info("agent.registered", agent_id=agent.agent_id, developer_id=agent.owner_id)
    broker.publish(
        "agent_registered",
        {
            "agent_id": agent.agent_id,
            "avid": agent.avid,
            "developer_id": agent.owner_id,
            "capabilities": capability_names(agent.capabilities),
        },
    )
    return RegisterAgentResponse(
        avid=agent.avid or "",
        agent_id=agent.agent_id,
        public_key=public_key_value,
        access_token=token,
        registration_timestamp=agent.registered_at,
    )


@router.get("/agents/{agent_id}/identity", response_model=AgentIdentityResponse)
@limiter.limit(rate_limit_str)
def agent_identity(
    request: Request,
    agent_id: str,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(verify_owner),
):
    key_row = db.query(AgentKey).filter(AgentKey.agent_id == agent_id).first()
    developer_id = current_agent.owner_id or ""
    return AgentIdentityResponse(
        avid=current_agent.avid or "",
        agent_id=current_agent.agent_id,
        developer_id=developer_id,
        public_key=key_row.public_key if key_row else "",
        capabilities=capability_names(current_agent.capabilities),
        created_at=current_agent.registered_at,
        reputation=current_agent.reputation_score,
        verified=bool(developer_id),
    )


@router.get("/agent/{agent_id}", response_model=AgentInfoResponse)
@limiter.limit(rate_limit_str)
def get_agent(
    request: Request, agent_id: str, db: Session = Depends(get_db), _: Agent = Depends(verify_owner)
):
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return AgentInfoResponse(
        agent_id=agent.agent_id,
        name=agent.name,
        reputation_score=agent.reputation_score,
        registered_capabilities=capability_names(agent.capabilities),
        total_tasks_executed=agent.total_tasks_executed,
        registered_at=agent.registered_at,
    )


@router.get("/agents")
@limiter.limit(rate_limit_str)
def list_agents(
    request: Request, db: Session = Depends(get_db), _: Agent = Depends(get_current_agent)
):
    agents = db.query(Agent).order_by(Agent.registered_at.desc()).limit(50).all()
    return [
        {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "reputation_score": agent.reputation_score,
            "capabilities": agent.capabilities or [],
            "registered_at": agent.registered_at,
            "total_tasks_executed": agent.total_tasks_executed,
        }
        for agent in agents
    ]


@router.get("/agents/active", response_model=list[ActiveAgentResponse])
@limiter.limit(rate_limit_str)
def active_agents(
    request: Request,
    db: Session = Depends(get_db),
    _: Agent = Depends(get_current_agent),
):
    now = datetime.utcnow()
    threshold = now - timedelta(minutes=5)
    agents = (
        db.query(Agent)
        .filter(Agent.last_heartbeat_at != None)  # noqa: E711
        .filter(Agent.last_heartbeat_at >= threshold)
        .order_by(Agent.last_heartbeat_at.desc())
        .limit(200)
        .all()
    )
    return [
        ActiveAgentResponse(
            agent_id=agent.agent_id,
            capabilities=[CapabilityItem(**item) for item in normalize_capabilities(agent.capabilities)],
            reputation=agent.reputation_score,
            last_heartbeat=agent.last_heartbeat_at,
        )
        for agent in agents
        if agent.last_heartbeat_at is not None
    ]


@router.get("/agents/{agent_id}/reputation", response_model=AgentReputationResponse)
@limiter.limit(rate_limit_str)
def agent_reputation(
    request: Request,
    agent_id: str,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(verify_owner),
):
    """Return explainable reputation signals + trust vector for the agent (self-only for MVP)."""
    # verify_owner guarantees agent_id == current_agent.agent_id; keep the query cheap and consistent.
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    tv = agent.trust_vector or {}
    # If a legacy DB row has no trust_vector yet, compute a best-effort one on read.
    peer_adj = aggregate_peer_adjustments(db, target_avid=getattr(agent, "avid", None) or "", window_days=30)
    if not tv:
        computed = compute_trust_vector(
            tasks_success=int(getattr(agent, "tasks_success", 0) or 0),
            tasks_failure=int(getattr(agent, "tasks_failure", 0) or 0),
            blocked_action_count=int(getattr(agent, "blocked_action_count", 0) or 0),
            invalid_signature_count=int(getattr(agent, "invalid_signature_count", 0) or 0),
            last_heartbeat_at=getattr(agent, "last_heartbeat_at", None),
            peer_adjustments=peer_adj,
        )
        tv = computed.as_dict()
    else:
        # Overlay peer adjustments on top of persisted trust vector, for explainability.
        try:
            base = compute_trust_vector(
                tasks_success=int(getattr(agent, "tasks_success", 0) or 0),
                tasks_failure=int(getattr(agent, "tasks_failure", 0) or 0),
                blocked_action_count=int(getattr(agent, "blocked_action_count", 0) or 0),
                invalid_signature_count=int(getattr(agent, "invalid_signature_count", 0) or 0),
                last_heartbeat_at=getattr(agent, "last_heartbeat_at", None),
                peer_adjustments=peer_adj,
            )
            tv = base.as_dict()
        except Exception:
            pass

    signals = AgentReputationSignals(
        tasks_success=int(getattr(agent, "tasks_success", 0) or 0),
        tasks_failure=int(getattr(agent, "tasks_failure", 0) or 0),
        total_tasks_executed=int(getattr(agent, "total_tasks_executed", 0) or 0),
        blocked_action_count=int(getattr(agent, "blocked_action_count", 0) or 0),
        invalid_signature_count=int(getattr(agent, "invalid_signature_count", 0) or 0),
        last_task_at=getattr(agent, "last_task_at", None),
        last_heartbeat_at=getattr(agent, "last_heartbeat_at", None),
    )

    return AgentReputationResponse(
        agent_id=agent.agent_id,
        avid=getattr(agent, "avid", None) or "",
        reputation_score=float(agent.reputation_score or 0.0),
        reputation_effective=float(
            effective_reputation(
                float(agent.reputation_score or 0.0),
                last_activity_at=getattr(agent, "last_task_at", None) or agent.registered_at,
            )
        ),
        success_rate=success_rate(signals.tasks_success, signals.tasks_failure),
        trust_vector=tv,
        trust_updated_at=getattr(agent, "trust_updated_at", None),
        signals=signals,
    )
