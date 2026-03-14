import json
from datetime import datetime, timedelta
from typing import Any, Dict, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import structlog

from ..core.rate_limiter import limiter, rate_limit_str
from ..database import get_db
from ..models import Agent, AgentTask, AuthorizationLog, AgentKey
from ..core.security import create_access_token, get_current_agent, pwd_context
from ..schemas.auth import TokenRequest, TokenResponse
from ..schemas.capability import capability_names
from firewall.action_firewall import evaluate_action
from ..core.policy_engine import evaluate_policies

router = APIRouter()
logger = structlog.get_logger()

class AuthorizationRequest(BaseModel):
    agent_id: str
    action_type: str
    action_payload: Dict[str, Any] = Field(default_factory=dict)


class AuthorizationResponse(BaseModel):
    decision: str
    reason: str


@router.post("/auth/token", response_model=TokenResponse)
@limiter.limit(rate_limit_str)
def issue_token(
    request: Request,
    payload: TokenRequest,
    db: Session = Depends(get_db),
):
    agent = db.query(Agent).filter(Agent.agent_id == payload.agent_id).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    key_ok = False
    if agent.public_key:
        try:
            key_ok = pwd_context.verify(payload.public_key, agent.public_key)
        except Exception:
            key_ok = False
    if not key_ok:
        key_row = db.query(AgentKey).filter(AgentKey.agent_id == agent.agent_id).first()
        if key_row and key_row.public_key == payload.public_key:
            key_ok = True

    if not key_ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent credentials")

    expires_in = int(payload.expires_in or 3600)
    claims = {
        "agent_id": agent.agent_id,
        "capabilities": capability_names(agent.capabilities),
        "reputation": agent.reputation_score,
    }
    token = create_access_token(claims, expires_seconds=expires_in)
    logger.info(
        "auth.token_issued",
        agent_id=agent.agent_id,
        expires_in=expires_in,
    )
    return TokenResponse(access_token=token, expires_in=expires_in)



@router.post("/authorize_action", response_model=AuthorizationResponse)
@limiter.limit(rate_limit_str)
def authorize_action(
    request: Request,
    payload: AuthorizationRequest,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    if payload.agent_id != current_agent.agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent mismatch")
    policy_result = evaluate_policies(db, payload.action_type, payload.action_payload or {})
    if policy_result:
        decision, reason, severity = policy_result
    else:
        decision, reason, severity = evaluate_action(payload.action_type, payload.action_payload or {})
    log = AuthorizationLog(
        agent_id=current_agent.agent_id,
        action_type=payload.action_type,
        payload=json.dumps(payload.action_payload or {}),
        decision=decision,
        reason=reason,
        blocked_reason=reason if decision != "allow" else None,
        severity=severity,
    )
    db.add(log)
    db.commit()
    return AuthorizationResponse(decision=decision, reason=reason)


@router.get("/authorization/logs")
@limiter.limit(rate_limit_str)
def authorization_logs(
    request: Request,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    logs = (
        db.query(AuthorizationLog)
        .filter(AuthorizationLog.agent_id == current_agent.agent_id)
        .order_by(AuthorizationLog.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "action_type": log.action_type,
            "decision": log.decision,
            "reason": log.reason,
            "timestamp": log.timestamp,
        }
        for log in logs
    ]


@router.get("/dashboard/summary")
@limiter.limit(rate_limit_str)
def dashboard_summary(request: Request, db: Session = Depends(get_db)):
    total_agents = db.query(Agent).count()
    now = datetime.utcnow()
    active_threshold = now - timedelta(minutes=5)
    active_agents = (
        db.query(Agent)
        .filter(Agent.last_heartbeat_at != None)
        .filter(Agent.last_heartbeat_at >= active_threshold)
        .all()
    )
    top_agents = (
        db.query(Agent)
        .order_by(Agent.reputation_score.desc())
        .limit(5)
        .all()
    )
    tasks = (
        db.query(AgentTask)
        .order_by(AgentTask.logged_at.desc())
        .limit(15)
        .all()
    )
    denied = (
        db.query(AuthorizationLog)
        .filter(AuthorizationLog.decision != "allow")
        .order_by(AuthorizationLog.timestamp.desc())
        .limit(10)
        .all()
    )
    return {
        "total_agents": total_agents,
        "active_agent_count": len(active_agents),
        "active_agents": [
            {
                "agent_id": agent.agent_id,
                "name": agent.name,
                "last_heartbeat": agent.last_heartbeat_at,
            }
            for agent in active_agents
        ],
        "top_agents": [
            {
                "agent_id": agent.agent_id,
                "name": agent.name,
                "reputation_score": agent.reputation_score,
                "capabilities": agent.capabilities or [],
            }
            for agent in top_agents
        ],
        "recent_tasks": [
            {
                "agent_id": task.agent_id,
                "description": task.task_description,
                "result_status": task.result_status,
                "execution_time": task.execution_time,
                "logged_at": task.logged_at,
            }
            for task in tasks
        ],
        "recent_blocked_actions": [
            {
                "agent_id": log.agent_id,
                "action_type": log.action_type,
                "decision": log.decision,
                "reason": log.reason,
                "blocked_reason": log.blocked_reason,
                "timestamp": log.timestamp,
            }
            for log in denied
        ],
    }
