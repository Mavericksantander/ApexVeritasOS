from fastapi import Depends, HTTPException

from ..core.security import get_current_agent
from ..models import Agent
from ..schemas.capability import capability_names


def verify_owner(agent_id: str, current_agent: Agent = Depends(get_current_agent)) -> Agent:
    if agent_id != current_agent.agent_id:
        raise HTTPException(status_code=403, detail="Agent mismatch")
    return current_agent


def require_admin(current_agent: Agent = Depends(get_current_agent)) -> Agent:
    if "admin" not in {name.lower() for name in capability_names(current_agent.capabilities)}:
        raise HTTPException(status_code=403, detail="Admin capability required")
    return current_agent
