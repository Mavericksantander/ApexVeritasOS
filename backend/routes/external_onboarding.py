from datetime import datetime
from uuid import uuid4
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.rate_limiter import limiter, rate_limit_str
from ..core.security import create_access_token, pwd_context
from ..database import get_db
from ..models import Agent

router = APIRouter()

_INVITE_CODES = {"AVOS-OPEN-2026", "PARTNER-KEY-01"}


class ExternalRegisterRequest(BaseModel):
    developer_id: str = Field(..., max_length=64)
    bot_name: str = Field(..., max_length=64)
    capabilities: list[str] = Field(default_factory=list)
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
        capabilities=payload.capabilities,
        public_key=pwd_context.hash(public_key_value),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    token = create_access_token({"agent_id": agent.agent_id})
    return ExternalRegisterResponse(
        agent_id=agent.agent_id,
        public_key=public_key_value,
        access_token=token,
        registered_at=agent.registered_at,
    )
