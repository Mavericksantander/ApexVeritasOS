from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.rate_limiter import limiter, rate_limit_str
from ..database import get_db
from ..models import Agent, AgentReputation, AgentTask
from ..core.security import get_current_agent

router = APIRouter()


class TaskLogRequest(BaseModel):
    agent_id: str
    task_description: str = Field(..., max_length=512)
    result_status: Literal["success", "failure"]
    execution_time: float = Field(default=0.0, ge=0)


class TaskLogResponse(BaseModel):
    reputation_score: float
    task_id: int


@router.post("/log_task", response_model=TaskLogResponse)
@limiter.limit(rate_limit_str)
def log_task(payload: TaskLogRequest, db: Session = Depends(get_db), current_agent: Agent = Depends(get_current_agent)):
    if payload.agent_id != current_agent.agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent mismatch")

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
    return TaskLogResponse(reputation_score=current_agent.reputation_score, task_id=task.id)


@router.get("/tasks/recent")
@limiter.limit(rate_limit_str)
def recent_tasks(limit: int = 20, db: Session = Depends(get_db), current_agent: Agent = Depends(get_current_agent)):
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
