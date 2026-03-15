from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AgentReputationSignals(BaseModel):
    tasks_success: int = 0
    tasks_failure: int = 0
    total_tasks_executed: int = 0
    blocked_action_count: int = 0
    invalid_signature_count: int = 0
    last_task_at: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None


class AgentReputationResponse(BaseModel):
    agent_id: str
    avid: str
    reputation_score: float
    reputation_effective: float
    success_rate: Optional[float] = None
    trust_vector: Dict[str, Any] = Field(default_factory=dict)
    trust_updated_at: Optional[datetime] = None
    signals: AgentReputationSignals

