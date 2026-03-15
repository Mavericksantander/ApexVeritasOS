from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ApexRuntimeClient:
    """HTTP client for the ApexVeritas Runtime gateway.

    Default transport uses `requests` to avoid adding new dependencies.
    For tests or advanced usage, you can inject an `httpx.Client`-compatible object.
    """

    base_url: str = "http://127.0.0.1:8010"
    timeout_s: float = 5.0
    headers: Optional[Dict[str, str]] = None
    httpx_client: Any = None

    def authorize_action(self, agent_ctx: Dict[str, Any], action_type: str, action_payload: Any) -> Dict[str, Any]:
        payload = {
            "agent_ctx": agent_ctx or {},
            "action_type": action_type,
            "action_payload": action_payload,
        }
        if self.httpx_client is not None:
            res = self.httpx_client.post("/authorize_action", json=payload)
            res.raise_for_status()
            return res.json()

        import requests

        url = self.base_url.rstrip("/") + "/authorize_action"
        res = requests.post(url, json=payload, headers=self.headers, timeout=self.timeout_s)
        res.raise_for_status()
        return res.json()

