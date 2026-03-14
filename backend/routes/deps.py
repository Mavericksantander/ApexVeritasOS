from fastapi import Depends, HTTPException

from ..core.security import get_current_agent
from ..models import Agent


def verify_owner(agent_id: str, current_agent: Agent = Depends(get_current_agent)) -> Agent:
    if agent_id != current_agent.agent_id:
        raise HTTPException(status_code=403, detail="Agent mismatch")
    return current_agent
