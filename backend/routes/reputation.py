from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.rate_limiter import limiter, rate_limit_str
from ..database import get_db
from ..models import Agent, AgentReputation
from ..core.security import get_current_agent
from ..core.events import broker

router = APIRouter()


class ReputationUpdateRequest(BaseModel):
    agent_id: str
    delta: float = Field(...)
    reason: str = Field(..., max_length=128)


class ReputationHistoryItem(BaseModel):
    delta: float
    reason: str
    created_at: str


@router.post("/update_reputation")
@limiter.limit(rate_limit_str)
def update_reputation(
    request: Request,
    payload: ReputationUpdateRequest,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    if payload.agent_id != current_agent.agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent mismatch")
    current_agent.reputation_score = round(current_agent.reputation_score + payload.delta, 2)
    rep_entry = AgentReputation(agent_id=current_agent.agent_id, delta=payload.delta, reason=payload.reason)
    db.add(rep_entry)
    db.commit()
    db.refresh(current_agent)
    broker.publish(
        "reputation_updated",
        {
            "agent_id": current_agent.agent_id,
            "avid": getattr(current_agent, "avid", None) or "",
            "delta": payload.delta,
            "reputation": current_agent.reputation_score,
            "reason": payload.reason,
        },
    )
    return {"reputation_score": current_agent.reputation_score}


@router.get("/reputation/history", response_model=List[ReputationHistoryItem])
@limiter.limit(rate_limit_str)
def reputation_history(
    request: Request,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    rows = (
        db.query(AgentReputation)
        .filter(AgentReputation.agent_id == current_agent.agent_id)
        .order_by(AgentReputation.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        ReputationHistoryItem(delta=row.delta, reason=row.reason or "", created_at=row.created_at.isoformat())
        for row in rows
    ]
