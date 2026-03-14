from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.rate_limiter import limiter, rate_limit_str
from ..database import get_db
from ..models import Agent
from ..core.security import get_current_agent

router = APIRouter()


@router.get("/agents/public")
@limiter.limit(rate_limit_str)
def public_agents(db: Session = Depends(get_db), _: Agent = Depends(get_current_agent)):
    """Return public metadata for agents so developers can discover reliable collaborators."""
    agents = (
        db.query(
            Agent.agent_id,
            Agent.name,
            Agent.reputation_score,
            Agent.total_tasks_executed,
            Agent.capabilities,
        )
        .order_by(Agent.reputation_score.desc())
        .all()
    )
    return [
        {
            "agent_id": row.agent_id,
            "agent_name": row.name,
            "reputation_score": row.reputation_score,
            "tasks_completed": row.total_tasks_executed,
            "capabilities": row.capabilities or [],
        }
        for row in agents
    ]


@router.get("/agents/search")
@limiter.limit(rate_limit_str)
def search_agents(
    capability: Optional[str] = Query(None, description="Filter agents that advertise the capability"),
    min_reputation: float = Query(0, ge=0, description="Minimum reputation score"),
    db: Session = Depends(get_db),
    _: Agent = Depends(get_current_agent),
):
    """Find agents whose capabilities and reputation match the provided filters."""
    query = db.query(Agent).filter(Agent.reputation_score >= min_reputation)
    if capability:
        query = query.filter(Agent.capabilities.contains([capability]))
    agents = query.order_by(Agent.reputation_score.desc()).limit(50).all()
    return [
        {
            "agent_id": agent.agent_id,
            "agent_name": agent.name,
            "reputation_score": agent.reputation_score,
            "tasks_completed": agent.total_tasks_executed,
            "capabilities": agent.capabilities or [],
        }
        for agent in agents
    ]
