from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class HandshakeInitRequest(BaseModel):
    to_avid: str = Field(..., min_length=8, max_length=80)
    message_id: str = Field(..., min_length=16, max_length=128)
    sent_at: datetime
    constraints: Dict[str, Any] = Field(default_factory=dict)
    signature: str = Field(..., min_length=16, max_length=20000)


class HandshakeInitResponse(BaseModel):
    session_id: str
    from_avid: str
    to_avid: str
    responder_nonce: str
    expires_at: datetime
    status: str


class HandshakeConfirmRequest(BaseModel):
    session_id: str = Field(..., min_length=16, max_length=128)
    signature: str = Field(..., min_length=16, max_length=20000)


class HandshakeConfirmResponse(BaseModel):
    session_id: str
    status: str
    confirmed_at: Optional[datetime] = None


class HandshakeInfoResponse(BaseModel):
    session_id: str
    from_avid: str
    to_avid: str
    initiator_nonce: str
    responder_nonce: str
    status: str
    expires_at: datetime
