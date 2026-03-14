from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.rate_limiter import limiter, rate_limit_str
from ..core.security import get_current_agent
from ..database import get_db
from ..models import Agent, AuthorizationLog

router = APIRouter()


@router.get("/metrics/blocked_actions")
@limiter.limit(rate_limit_str)
def blocked_actions(db: Session = Depends(get_db), _: Agent = Depends(get_current_agent)):
    """Expose a simple counter of authorization events that were not allowed."""
    blocked_count = (
        db.query(AuthorizationLog)
        .filter(AuthorizationLog.decision != "allow")
        .count()
    )
    return {"blocked_actions_count": blocked_count}
