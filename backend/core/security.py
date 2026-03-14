from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Agent
from .config import settings
from .logging import bind_request
from structlog.contextvars import merge_contextvars

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security_scheme = HTTPBearer()

_rate_limit_store: Dict[str, Dict[str, Any]] = defaultdict(
    lambda: {"count": 0, "reset": datetime.utcnow() + timedelta(seconds=settings.AVOS_RATE_WINDOW)}
)


def enforce_rate_limit(agent_id: str) -> None:
    entry = _rate_limit_store[agent_id]
    now = datetime.utcnow()
    if now >= entry["reset"]:
        entry["count"] = 0
        entry["reset"] = now + timedelta(seconds=settings.AVOS_RATE_WINDOW)
    entry["count"] += 1
    if entry["count"] > settings.AVOS_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for this agent",
        )


def create_access_token(data: dict[str, Any], expires_minutes: int = 60) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def verify_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def get_current_agent(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme), db: Session = Depends(get_db)
) -> Agent:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization token")
    payload = verify_token(credentials.credentials)
    agent_id = payload.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token payload missing agent_id")
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    enforce_rate_limit(agent.agent_id)
    context = merge_contextvars()
    bind_request(
        request_id=context.get("request_id", "unknown"),
        agent_id=agent.agent_id,
        reputation_delta=agent.reputation_score,
    )
    return agent
