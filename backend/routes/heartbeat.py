from datetime import datetime

from typing import Optional

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.rate_limiter import limiter, rate_limit_str
from ..database import get_db
from ..models import Agent, AgentHeartbeat
from .deps import verify_owner
from ..core.trust_vector import compute_trust_vector

router = APIRouter()


class HeartbeatRequest(BaseModel):
    model: Optional[str] = Field(None, max_length=64)
    version: Optional[str] = Field(None, max_length=32)
    status: str = Field("active", max_length=32)


@router.post("/agents/{agent_id}/heartbeat", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(rate_limit_str)
def record_heartbeat(
    request: Request,
    agent_id: str,
    payload: HeartbeatRequest,
    db: Session = Depends(get_db),
    _: Agent = Depends(verify_owner),
):
    """Persist agent heartbeat metadata and timestamp for operational visibility."""
    now = datetime.utcnow()
    heartbeat = AgentHeartbeat(
        agent_id=agent_id,
        model=payload.model,
        version=payload.version,
        status=payload.status,
        reported_at=now,
    )
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if agent:
        agent.last_heartbeat_at = now
        tv = compute_trust_vector(
            tasks_success=int(getattr(agent, "tasks_success", 0) or 0),
            tasks_failure=int(getattr(agent, "tasks_failure", 0) or 0),
            blocked_action_count=int(getattr(agent, "blocked_action_count", 0) or 0),
            invalid_signature_count=int(getattr(agent, "invalid_signature_count", 0) or 0),
            last_heartbeat_at=now,
        )
        agent.trust_vector = tv.as_dict()
        agent.trust_updated_at = now
    db.add(heartbeat)
    db.commit()
    return {
        "agent_id": agent_id,
        "reported_at": now,
        "status": payload.status,
    }
