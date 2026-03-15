from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AttestationCreateRequest(BaseModel):
    """Create an issuer attestation for an agent (signed by issuer key)."""

    avid: str = Field(..., min_length=8, max_length=80)
    issuer: str = Field(..., min_length=2, max_length=80)
    claim_type: str = Field(..., min_length=2, max_length=64)
    claim_value: Dict[str, Any] = Field(default_factory=dict)
    signature: str = Field(..., min_length=16, max_length=20000)


class AttestationResponse(BaseModel):
    id: int
    avid: str
    issuer: str
    claim_type: str
    claim_value: Dict[str, Any]
    verified: bool
    created_at: datetime


class RegistryAgentItem(BaseModel):
    avid: str
    agent_name: str
    capabilities: list[Dict[str, Any]]
    reputation_score: float
    reputation_effective: float
    success_rate: Optional[float] = None
    verification_level: str
    verified_by_avos: bool
    active: bool
    last_heartbeat_at: Optional[datetime] = None
    last_task_at: Optional[datetime] = None
    attestations: list[AttestationResponse] = Field(default_factory=list)

