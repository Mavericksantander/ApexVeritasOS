from datetime import datetime
from uuid import uuid4
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.rate_limiter import limiter, rate_limit_str
from ..core.security import create_access_token, get_current_agent, pwd_context
from ..database import get_db
from ..models import Agent
from .deps import verify_owner

router = APIRouter()


class RegisterAgentRequest(BaseModel):
    agent_name: str = Field(..., max_length=64)
    owner_id: str = Field(..., max_length=64)
    capabilities: list[str] = Field(default_factory=list)


class RegisterAgentResponse(BaseModel):
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
def register_agent(payload: RegisterAgentRequest, db: Session = Depends(get_db)):
    agent_id = str(uuid4())
    public_key_value = secrets.token_urlsafe(32)
    agent = Agent(
        agent_id=agent_id,
        name=payload.agent_name,
        owner_id=payload.owner_id,
        capabilities=payload.capabilities,
        public_key=pwd_context.hash(public_key_value),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    token = create_access_token({"agent_id": agent.agent_id})
    return RegisterAgentResponse(
        agent_id=agent.agent_id,
        public_key=public_key_value,
        access_token=token,
        registration_timestamp=agent.registered_at,
    )


@router.get("/agent/{agent_id}", response_model=AgentInfoResponse)
@limiter.limit(rate_limit_str)
def get_agent(agent_id: str, db: Session = Depends(get_db), _: Agent = Depends(verify_owner)):
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return AgentInfoResponse(
        agent_id=agent.agent_id,
        name=agent.name,
        reputation_score=agent.reputation_score,
        registered_capabilities=agent.capabilities or [],
        total_tasks_executed=agent.total_tasks_executed,
        registered_at=agent.registered_at,
    )


@router.get("/agents")
@limiter.limit(rate_limit_str)
def list_agents(db: Session = Depends(get_db), _: Agent = Depends(get_current_agent)):
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
