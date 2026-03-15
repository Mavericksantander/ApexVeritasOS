from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.rate_limiter import limiter, rate_limit_str
from ..database import get_db
from ..models import Agent, AgentKey, AgentReputation, AgentTask
from ..core.security import get_current_agent
from ..core.events import broker
from ..core.signatures import canonical_json_bytes, sha256_digest, verify_ecdsa_p256_sha256, verify_hmac_sha256

router = APIRouter()


class TaskLogRequest(BaseModel):
    agent_id: str
    task_description: str = Field(..., max_length=512)
    result_status: Literal["success", "failure"]
    execution_time: float = Field(default=0.0, ge=0)
    signature: Optional[str] = Field(default=None, max_length=8192)


class TaskLogByIdRequest(BaseModel):
    task_description: str = Field(..., max_length=512)
    result_status: Literal["success", "failure"]
    execution_time: float = Field(default=0.0, ge=0)
    signature: Optional[str] = Field(default=None, max_length=8192)


class TaskLogResponse(BaseModel):
    reputation_score: float
    task_id: int


def _log_task_impl(
    request: Request,
    payload: TaskLogRequest,
    db: Session,
    current_agent: Agent,
):
    if payload.agent_id != current_agent.agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent mismatch")

    if payload.signature:
        key_row = db.query(AgentKey).filter(AgentKey.agent_id == current_agent.agent_id).first()
        if not key_row:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent signing key not registered")
        task_data = {
            "agent_id": current_agent.agent_id,
            "task_description": payload.task_description,
            "result_status": payload.result_status,
            "execution_time": payload.execution_time,
        }
        digest = sha256_digest(canonical_json_bytes(task_data))
        key_value = key_row.public_key
        ok = False
        if key_value.strip().startswith("-----BEGIN PUBLIC KEY-----"):
            ok = verify_ecdsa_p256_sha256(key_value, digest, payload.signature)
        else:
            ok = verify_hmac_sha256(key_value, digest, payload.signature)

        if not ok:
            delta = -1.0
            current_agent.reputation_score = round(current_agent.reputation_score + delta, 2)
            rep_entry = AgentReputation(
                agent_id=current_agent.agent_id,
                delta=delta,
                reason="Invalid task signature",
            )
            db.add(rep_entry)
            db.commit()
            db.refresh(current_agent)
            broker.publish(
                "reputation_updated",
                {
                    "agent_id": current_agent.agent_id,
                    "avid": getattr(current_agent, "avid", None) or "",
                    "delta": delta,
                    "reputation": current_agent.reputation_score,
                    "reason": rep_entry.reason,
                },
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    task = AgentTask(
        agent_id=current_agent.agent_id,
        task_description=payload.task_description,
        result_status=payload.result_status,
        execution_time=payload.execution_time,
    )
    db.add(task)

    delta = 0.5 if payload.result_status == "success" else -1.0
    current_agent.reputation_score = round(current_agent.reputation_score + delta, 2)
    current_agent.total_tasks_executed += 1
    rep_entry = AgentReputation(
        agent_id=current_agent.agent_id,
        delta=delta,
        reason=f"Task {payload.result_status}",
    )
    db.add(rep_entry)
    db.commit()
    db.refresh(current_agent)
    db.refresh(task)
    broker.publish(
        "task_completed",
        {
            "agent_id": current_agent.agent_id,
            "avid": getattr(current_agent, "avid", None) or "",
            "task_id": task.id,
            "result_status": payload.result_status,
            "reputation": current_agent.reputation_score,
        },
    )
    broker.publish(
        "reputation_updated",
        {
            "agent_id": current_agent.agent_id,
            "avid": getattr(current_agent, "avid", None) or "",
            "delta": delta,
            "reputation": current_agent.reputation_score,
            "reason": rep_entry.reason,
        },
    )
    return TaskLogResponse(reputation_score=current_agent.reputation_score, task_id=task.id)


@router.post("/log_task", response_model=TaskLogResponse)
@limiter.limit(rate_limit_str)
def log_task(
    request: Request,
    payload: TaskLogRequest,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    return _log_task_impl(request, payload, db=db, current_agent=current_agent)


@router.post("/agent/{agent_id}/log_task", response_model=TaskLogResponse)
@limiter.limit(rate_limit_str)
def log_task_by_agent_id(
    request: Request,
    agent_id: str,
    payload: TaskLogByIdRequest,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    return _log_task_impl(
        request,
        TaskLogRequest(
            agent_id=agent_id,
            task_description=payload.task_description,
            result_status=payload.result_status,
            execution_time=payload.execution_time,
            signature=payload.signature,
        ),
        db=db,
        current_agent=current_agent,
    )


@router.get("/tasks/recent")
@limiter.limit(rate_limit_str)
def recent_tasks(
    request: Request,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    tasks = (
        db.query(AgentTask)
        .filter(AgentTask.agent_id == current_agent.agent_id)
        .order_by(AgentTask.logged_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "task_id": task.id,
            "description": task.task_description,
            "result_status": task.result_status,
            "execution_time": task.execution_time,
            "logged_at": task.logged_at,
        }
        for task in tasks
    ]
