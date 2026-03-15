import json
from datetime import datetime, timedelta
from typing import Any, Dict, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func
import structlog

from ..core.rate_limiter import limiter, rate_limit_str
from ..database import get_db
from ..models import Agent, AgentTask, AuthorizationLog, AgentKey, AgentReputation
from ..core.security import create_access_token, get_current_agent, pwd_context
from ..schemas.auth import TokenRequest, TokenResponse
from ..schemas.capability import capability_names
from firewall.action_firewall import evaluate_action
from ..core.policy_engine import evaluate_policies
from ..core.constitution import evaluate_action_against_constitution
from ..core.events import broker
from ..core.reputation_metrics import effective_reputation, success_rate
from ..core.audit_chain import compute_chain_hash
from ..core.trust_vector import compute_trust_vector

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

    constitution = evaluate_action_against_constitution(
        avid=getattr(current_agent, "avid", None) or current_agent.agent_id,
        action_type=payload.action_type,
        action_payload=payload.action_payload or {},
        agent_reputation=current_agent.reputation_score,
    )
    if not constitution.allowed:
        # For now, any constitutional "verification" also blocks execution here; the caller can surface it to a human.
        decision = "deny"
        reason = constitution.explanation
        severity = constitution.severity
        broker.publish("constitution_event", constitution.witness)
    else:
        policy_result = evaluate_policies(db, payload.action_type, payload.action_payload or {})
        if policy_result:
            decision, reason, severity = policy_result
        else:
            decision, reason, severity = evaluate_action(payload.action_type, payload.action_payload or {})
    if decision != "allow":
        current_agent.blocked_action_count = int(getattr(current_agent, "blocked_action_count", 0) or 0) + 1
    tv = compute_trust_vector(
        tasks_success=int(getattr(current_agent, "tasks_success", 0) or 0),
        tasks_failure=int(getattr(current_agent, "tasks_failure", 0) or 0),
        blocked_action_count=int(getattr(current_agent, "blocked_action_count", 0) or 0),
        invalid_signature_count=int(getattr(current_agent, "invalid_signature_count", 0) or 0),
        last_heartbeat_at=getattr(current_agent, "last_heartbeat_at", None),
    )
    current_agent.trust_vector = tv.as_dict()
    current_agent.trust_updated_at = datetime.utcnow()
    prev = (
        db.query(AuthorizationLog.entry_hash)
        .filter(AuthorizationLog.agent_id == current_agent.agent_id)
        .order_by(AuthorizationLog.id.desc())
        .limit(1)
        .scalar()
    )
    entry_hash = compute_chain_hash(
        prev_hash=prev,
        namespace="authorization_log",
        fields={
            "agent_id": current_agent.agent_id,
            "avid": getattr(current_agent, "avid", None) or "",
            "action_type": payload.action_type,
            "payload": payload.action_payload or {},
            "decision": decision,
            "reason": reason,
            "severity": severity,
        },
    )
    log = AuthorizationLog(
        agent_id=current_agent.agent_id,
        action_type=payload.action_type,
        payload=json.dumps(payload.action_payload or {}),
        decision=decision,
        reason=reason,
        blocked_reason=reason if decision != "allow" else None,
        severity=severity,
        prev_hash=prev,
        entry_hash=entry_hash,
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

    # Derived reputation window (last 30 days)
    rep_threshold = now - timedelta(days=30)
    agent_ids_for_rep = {a.agent_id for a in active_agents} | {a.agent_id for a in top_agents}
    rep_30d_map: dict[str, float] = {}
    if agent_ids_for_rep:
        rep_rows = (
            db.query(AgentReputation.agent_id, func.coalesce(func.sum(AgentReputation.delta), 0.0))
            .filter(AgentReputation.created_at >= rep_threshold)
            .filter(AgentReputation.agent_id.in_(list(agent_ids_for_rep)))
            .group_by(AgentReputation.agent_id)
            .all()
        )
        rep_30d_map = {agent_id: float(total) for agent_id, total in rep_rows}

    # Top blocked reasons (ops-friendly)
    reason_rows = (
        db.query(func.coalesce(AuthorizationLog.blocked_reason, AuthorizationLog.reason), func.count(AuthorizationLog.id))
        .filter(AuthorizationLog.decision != "allow")
        .group_by(func.coalesce(AuthorizationLog.blocked_reason, AuthorizationLog.reason))
        .order_by(func.count(AuthorizationLog.id).desc())
        .limit(8)
        .all()
    )
    top_blocked_reasons = [{"reason": (r or "Unknown"), "count": int(c)} for r, c in reason_rows]

    ids_for_avid = {t.agent_id for t in tasks} | {l.agent_id for l in denied}
    avid_map: dict[str, str] = {}
    if ids_for_avid:
        avid_rows = db.query(Agent.agent_id, Agent.avid).filter(Agent.agent_id.in_(list(ids_for_avid))).all()
        avid_map = {row.agent_id: (row.avid or "") for row in avid_rows}
    return {
        "total_agents": total_agents,
        "active_agent_count": len(active_agents),
        "active_agents": [
            {
                "agent_id": agent.agent_id,
                "avid": getattr(agent, "avid", None) or "",
                "name": agent.name,
                "reputation_score": agent.reputation_score,
                "reputation_effective": round(
                    effective_reputation(agent.reputation_score, last_activity_at=getattr(agent, "last_task_at", None) or agent.registered_at),
                    4,
                ),
                "tasks_completed": agent.total_tasks_executed,
                "success_rate": success_rate(getattr(agent, "tasks_success", 0) or 0, getattr(agent, "tasks_failure", 0) or 0),
                "invalid_signature_count": int(getattr(agent, "invalid_signature_count", 0) or 0),
                "blocked_action_count": int(getattr(agent, "blocked_action_count", 0) or 0),
                "last_30d_delta": rep_30d_map.get(agent.agent_id, 0.0),
                "last_heartbeat": agent.last_heartbeat_at,
            }
            for agent in active_agents
        ],
        "top_agents": [
            {
                "agent_id": agent.agent_id,
                "avid": getattr(agent, "avid", None) or "",
                "name": agent.name,
                "reputation_score": agent.reputation_score,
                "reputation_effective": round(
                    effective_reputation(agent.reputation_score, last_activity_at=getattr(agent, "last_task_at", None) or agent.registered_at),
                    4,
                ),
                "capabilities": agent.capabilities or [],
                "tasks_completed": agent.total_tasks_executed,
                "success_rate": success_rate(getattr(agent, "tasks_success", 0) or 0, getattr(agent, "tasks_failure", 0) or 0),
                "invalid_signature_count": int(getattr(agent, "invalid_signature_count", 0) or 0),
                "blocked_action_count": int(getattr(agent, "blocked_action_count", 0) or 0),
                "last_30d_delta": rep_30d_map.get(agent.agent_id, 0.0),
                "last_task_at": getattr(agent, "last_task_at", None),
            }
            for agent in top_agents
        ],
        "recent_tasks": [
            {
                "agent_id": task.agent_id,
                "avid": avid_map.get(task.agent_id, ""),
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
                "avid": avid_map.get(log.agent_id, ""),
                "action_type": log.action_type,
                "decision": log.decision,
                "reason": log.reason,
                "blocked_reason": log.blocked_reason,
                "timestamp": log.timestamp,
            }
            for log in denied
        ],
        "top_blocked_reasons": top_blocked_reasons,
    }
