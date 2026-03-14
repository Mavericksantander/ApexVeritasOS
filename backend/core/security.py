from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Agent
from .config import settings
from .logging import bind_request

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

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


def create_access_token(
    data: dict[str, Any],
    *,
    expires_minutes: int | None = None,
    expires_seconds: int | None = None,
) -> str:
    to_encode = data.copy()
    if expires_seconds is None:
        expires_seconds = 3600 if expires_minutes is None else int(expires_minutes) * 60
    expire = datetime.utcnow() + timedelta(seconds=int(expires_seconds))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def verify_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def get_current_agent(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Agent:
    payload = verify_token(token)
    agent_id = payload.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token payload missing agent_id")
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    enforce_rate_limit(agent.agent_id)
    bind_request(
        request_id=getattr(request.state, "request_id", "unknown"),
        agent_id=agent.agent_id,
        reputation_delta=agent.reputation_score,
    )
    return agent
