from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.rate_limiter import limiter, rate_limit_str
from ..database import get_db
from ..models import A2AMessage, A2ASession, Agent, AuthorizationLog, AgentTask

router = APIRouter()


@router.get("/observatory/activity")
@limiter.limit(rate_limit_str)
def activity(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Public operational activity feed (safe fields only)."""
    tasks = db.query(AgentTask).order_by(AgentTask.logged_at.desc()).limit(limit).all()
    auth = db.query(AuthorizationLog).order_by(AuthorizationLog.timestamp.desc()).limit(limit).all()
    msgs = db.query(A2AMessage).order_by(A2AMessage.created_at.desc()).limit(limit).all()

    avid_map = {a.agent_id: (a.avid or "") for a in db.query(Agent.agent_id, Agent.avid).all()}

    return {
        "tasks": [
            {
                "time": t.logged_at,
                "agent_id": t.agent_id,
                "avid": avid_map.get(t.agent_id, ""),
                "result_status": t.result_status,
                "execution_time": t.execution_time,
                "description": t.task_description,
            }
            for t in tasks
        ],
        "authorizations": [
            {
                "time": a.timestamp,
                "agent_id": a.agent_id,
                "avid": avid_map.get(a.agent_id, ""),
                "action_type": a.action_type,
                "decision": a.decision,
                "severity": a.severity,
                "reason": a.blocked_reason or a.reason,
                "entry_hash": a.entry_hash,
            }
            for a in auth
        ],
        "a2a_messages": [
            {
                "time": m.created_at,
                "from_avid": m.from_avid,
                "to_avid": m.to_avid,
                "message_type": m.message_type,
                "message_id": m.message_id,
                "verified": bool(m.verified),
                "entry_hash": m.entry_hash,
            }
            for m in msgs
        ],
    }


@router.get("/observatory/graph")
@limiter.limit(rate_limit_str)
def graph(
    request: Request,
    since_minutes: int = Query(60, ge=1, le=10080),
    db: Session = Depends(get_db),
):
    """Return a lightweight agent interaction graph.

    Nodes: agents (avid, name)
    Edges: A2A messages and sessions (from_avid -> to_avid)
    """
    since = datetime.utcnow() - timedelta(minutes=since_minutes)
    agents = db.query(Agent).order_by(Agent.reputation_score.desc()).limit(1000).all()
    msgs = db.query(A2AMessage).filter(A2AMessage.created_at >= since).order_by(A2AMessage.id.desc()).limit(2000).all()
    sessions = db.query(A2ASession).filter(A2ASession.created_at >= since).order_by(A2ASession.id.desc()).limit(2000).all()

    nodes = [
        {
            "avid": a.avid,
            "name": a.name,
            "reputation": a.reputation_score,
            "last_heartbeat_at": a.last_heartbeat_at,
        }
        for a in agents
        if a.avid
    ]
    edges = []
    for m in msgs:
        edges.append(
            {
                "type": "message",
                "from_avid": m.from_avid,
                "to_avid": m.to_avid,
                "time": m.created_at,
                "label": m.message_type,
                "verified": bool(m.verified),
            }
        )
    for s in sessions:
        edges.append(
            {
                "type": "session",
                "from_avid": s.initiator_avid,
                "to_avid": s.responder_avid,
                "time": s.created_at,
                "label": s.status,
            }
        )
    return {"since": since, "nodes": nodes, "edges": edges}


@router.get("/observatory/trust_analytics")
@limiter.limit(rate_limit_str)
def trust_analytics(
    request: Request,
    db: Session = Depends(get_db),
):
    """Very small analytics: blocked counts and active agents."""
    blocked = db.query(func.count(AuthorizationLog.id)).filter(AuthorizationLog.decision != "allow").scalar() or 0
    total = db.query(func.count(Agent.agent_id)).scalar() or 0
    active_threshold = datetime.utcnow() - timedelta(minutes=5)
    active = (
        db.query(func.count(Agent.agent_id))
        .filter(Agent.last_heartbeat_at != None)  # noqa: E711
        .filter(Agent.last_heartbeat_at >= active_threshold)
        .scalar()
        or 0
    )
    return {"total_agents": int(total), "active_agents": int(active), "blocked_actions": int(blocked)}

