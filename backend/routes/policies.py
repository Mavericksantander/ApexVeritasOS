from __future__ import annotations

from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.rate_limiter import limiter, rate_limit_str
from ..core.security import get_current_agent
from ..database import get_db
from ..models import Policy
from .deps import require_admin

router = APIRouter()
logger = structlog.get_logger()


class PolicyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    pattern: str = Field(..., min_length=1, max_length=2048)
    action: Literal["deny", "allow", "require_approval"] = "deny"
    severity: int = Field(5, ge=1, le=10)


@router.get("/policies")
@limiter.limit(rate_limit_str)
def list_policies(
    request: Request,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_agent),
):
    rows = db.query(Policy).order_by(Policy.severity.desc(), Policy.created_at.desc()).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "pattern": row.pattern,
            "action": row.action,
            "severity": row.severity,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.post("/policies", status_code=status.HTTP_201_CREATED)
@limiter.limit(rate_limit_str)
def create_policy(
    request: Request,
    payload: PolicyCreateRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    exists = db.query(Policy).filter(Policy.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=409, detail="Policy name already exists")
    policy = Policy(
        name=payload.name,
        pattern=payload.pattern,
        action=payload.action,
        severity=payload.severity,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    logger.info("policy.created", name=policy.name, severity=policy.severity, action=policy.action)
    return {
        "id": policy.id,
        "name": policy.name,
        "pattern": policy.pattern,
        "action": policy.action,
        "severity": policy.severity,
        "created_at": policy.created_at,
    }

