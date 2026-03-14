from datetime import datetime
from uuid import uuid4
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import structlog

from ..core.rate_limiter import limiter, rate_limit_str
from ..core.security import create_access_token, pwd_context
from ..database import get_db
from ..models import Agent, AgentKey
from ..core.events import broker
from ..schemas.capability import capability_names, normalize_capabilities

router = APIRouter()
logger = structlog.get_logger()

_INVITE_CODES = {"AVOS-OPEN-2026", "PARTNER-KEY-01"}


class ExternalRegisterRequest(BaseModel):
    developer_id: str = Field(..., max_length=64)
    bot_name: str = Field(..., max_length=64)
    capabilities: list[object] = Field(default_factory=list)
    invite_code: str = Field(..., min_length=6)


class ExternalRegisterResponse(BaseModel):
    agent_id: str
    public_key: str
    access_token: str
    token_type: str = "bearer"
    registered_at: datetime


@router.post("/external/register_agent", response_model=ExternalRegisterResponse)
@limiter.limit(rate_limit_str)
def external_register_agent(
    request: Request,
    payload: ExternalRegisterRequest,
    db: Session = Depends(get_db),
):
    """Invite-protected onboarding endpoint for OpenClaw bots.

    OpenClaw agents should call this over HTTPS (or via `ngrok http 8000` for local dev)
    with `developer_id`, `bot_name`, capabilities list, and a shared `invite_code`.
    """
    if payload.invite_code not in _INVITE_CODES:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid invite code",
        )
    public_key_value = secrets.token_urlsafe(32)
    agent = Agent(
        agent_id=str(uuid4()),
        name=payload.bot_name,
        owner_id=payload.developer_id,
        capabilities=normalize_capabilities(payload.capabilities),
        public_key=pwd_context.hash(public_key_value),
    )
    db.add(agent)
    db.add(AgentKey(agent_id=agent.agent_id, public_key=public_key_value))
    db.commit()
    db.refresh(agent)
    token = create_access_token(
        {"agent_id": agent.agent_id, "capabilities": capability_names(agent.capabilities), "reputation": agent.reputation_score}
    )
    logger.info("agent.registered_external", agent_id=agent.agent_id, developer_id=agent.owner_id)
    broker.publish(
        "agent_registered",
        {
            "agent_id": agent.agent_id,
            "developer_id": agent.owner_id,
            "capabilities": capability_names(agent.capabilities),
        },
    )
    return ExternalRegisterResponse(
        agent_id=agent.agent_id,
        public_key=public_key_value,
        access_token=token,
        registered_at=agent.registered_at,
    )
