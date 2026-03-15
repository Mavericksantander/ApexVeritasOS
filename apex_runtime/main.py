from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .core import authorize_action


def _default_policy_file() -> Path:
    # Prefer the bundled policy pack if present; fall back to legacy policies.yaml.
    packaged = Path(__file__).with_name("policies") / "default.yaml"
    if packaged.exists():
        return packaged
    return Path(__file__).with_name("policies.yaml")


class ActionRequest(BaseModel):
    agent_ctx: Dict[str, Any] = Field(default_factory=dict)
    action_type: str
    action_payload: Any = Field(default_factory=dict)


app = FastAPI(title="ApexVeritas Runtime", version="0.1.0")


@app.post("/authorize_action")
async def authorize(req: ActionRequest):
    policy_file = os.getenv("APEX_POLICY_FILE")
    audit_log_path = os.getenv("APEX_AUDIT_LOG_PATH", "audit.log")
    return authorize_action(
        req.agent_ctx,
        req.action_type,
        req.action_payload,
        policy_file=policy_file or _default_policy_file(),
        audit_log_path=audit_log_path,
    )

