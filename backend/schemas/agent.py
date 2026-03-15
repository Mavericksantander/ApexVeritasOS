from datetime import datetime

from pydantic import BaseModel

from .capability import CapabilityItem


class AgentIdentityResponse(BaseModel):
    avid: str
    agent_id: str
    developer_id: str
    public_key: str
    capabilities: list[str]
    created_at: datetime
    reputation: float
    verified: bool


class ActiveAgentResponse(BaseModel):
    agent_id: str
    capabilities: list[CapabilityItem]
    reputation: float
    last_heartbeat: datetime
