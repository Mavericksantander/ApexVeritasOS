from typing import Optional

import requests


class AVOSAgent:
    def __init__(
        self,
        agent_name: str,
        owner_id: str = "local",
        capabilities: Optional[list[str]] = None,
        base_url: str = "http://127.0.0.1:8000",
    ):
        self.agent_name = agent_name
        self.owner_id = owner_id
        self.capabilities = capabilities or []
        self.base_url = base_url.rstrip("/")
        self.agent_id: Optional[str] = None
        self.public_key: Optional[str] = None
        self.access_token: Optional[str] = None

    def _headers(self) -> dict[str, str]:
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    def register_agent(self) -> dict:
        payload = {
            "agent_name": self.agent_name,
            "owner_id": self.owner_id,
            "capabilities": self.capabilities,
        }
        res = requests.post(f"{self.base_url}/register_agent", json=payload)
        res.raise_for_status()
        data = res.json()
        self.agent_id = data["agent_id"]
        self.public_key = data["public_key"]
        self.access_token = data.get("access_token")
        return data

    def log_task(self, description: str, result_status: str = "success", execution_time: float = 0.0) -> dict:
        if not self.agent_id or not self.access_token:
            raise RuntimeError("Register the agent before logging tasks")
        payload = {
            "agent_id": self.agent_id,
            "task_description": description,
            "result_status": result_status,
            "execution_time": execution_time,
        }
        res = requests.post(f"{self.base_url}/log_task", headers=self._headers(), json=payload)
        res.raise_for_status()
        return res.json()

    def authorize_action(self, action_type: str, action_payload: Optional[dict] = None) -> dict:
        if not self.agent_id or not self.access_token:
            raise RuntimeError("Register the agent before requesting authorization")
        payload = {
            "agent_id": self.agent_id,
            "action_type": action_type,
            "action_payload": action_payload or {},
        }
        res = requests.post(f"{self.base_url}/authorize_action", headers=self._headers(), json=payload)
        res.raise_for_status()
        return res.json()

    def send_heartbeat(self, model: Optional[str] = None, version: Optional[str] = None, status: str = "active") -> dict:
        if not self.agent_id or not self.access_token:
            raise RuntimeError("Register the agent before sending heartbeats")
        payload = {
            "model": model,
            "version": version,
            "status": status,
        }
        res = requests.post(
            f"{self.base_url}/agents/{self.agent_id}/heartbeat",
            headers=self._headers(),
            json=payload,
        )
        res.raise_for_status()
        return res.json()
