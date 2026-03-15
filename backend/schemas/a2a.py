from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class RegisterSigningKeyRequest(BaseModel):
    """Register a signing public key for agent-to-agent verification (ECDSA P-256).

    This is distinct from the onboarding credential returned as `public_key`.
    """

    public_key_pem: str = Field(..., min_length=64, max_length=10000)


class RegisterSigningKeyResponse(BaseModel):
    agent_id: str
    avid: str
    created_at: datetime


class A2ASendRequest(BaseModel):
    """Agent-to-agent message relay payload.

    The signature is computed over a canonical JSON of:
    {from_avid,to_avid,message_id,sent_at,message_type,payload}
    using the agent's private key that matches the registered public_key_pem.
    """

    to_avid: str = Field(..., min_length=8, max_length=80)
    message_id: str = Field(..., min_length=16, max_length=128)
    sent_at: datetime
    message_type: str = Field(..., min_length=1, max_length=64)
    payload: Dict[str, Any] = Field(default_factory=dict)
    signature: str = Field(..., min_length=16, max_length=20000)


class A2ASendResponse(BaseModel):
    status: str
    stored_id: int
    verified: bool


class A2AMessageItem(BaseModel):
    id: int
    from_avid: str
    to_avid: str
    message_id: str
    message_type: str
    sent_at: datetime
    payload: Dict[str, Any]
    payload_sha256: str
    verified: bool
    created_at: datetime
    delivered_at: Optional[datetime] = None

