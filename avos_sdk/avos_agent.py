from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Optional

import requests


class AVOSAgent:
    def __init__(
        self,
        agent_name: str,
        owner_id: str = "local",
        capabilities: Optional[list[object]] = None,
        base_url: str = "http://127.0.0.1:8000",
        signing_private_key_pem: Optional[str] = None,
    ):
        self.agent_name = agent_name
        self.owner_id = owner_id
        self.capabilities = capabilities or []
        self.base_url = base_url.rstrip("/")
        self.agent_id: Optional[str] = None
        self.public_key: Optional[str] = None
        self.access_token: Optional[str] = None
        self.signing_private_key_pem = signing_private_key_pem

    def _headers(self) -> dict[str, str]:
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    def fetch_token(self, expires_in: int = 3600) -> dict:
        if not self.agent_id or not self.public_key:
            raise RuntimeError("Register the agent before requesting a token")
        payload = {"agent_id": self.agent_id, "public_key": self.public_key, "expires_in": expires_in}
        res = requests.post(f"{self.base_url}/auth/token", json=payload)
        res.raise_for_status()
        data = res.json()
        self.access_token = data["access_token"]
        return data

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
        try:
            self.fetch_token()
        except Exception:
            pass
        return data

    def _task_signature(self, task_data: dict) -> Optional[str]:
        message = json.dumps(task_data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        digest = hashlib.sha256(message).digest()
        if self.signing_private_key_pem:
            try:
                from cryptography.hazmat.primitives import hashes, serialization
                from cryptography.hazmat.primitives.asymmetric import ec, utils

                priv = serialization.load_pem_private_key(self.signing_private_key_pem.encode("utf-8"), password=None)
                signature = priv.sign(digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
                return base64.b64encode(signature).decode("utf-8")
            except Exception:
                return None
        if self.public_key:
            mac = hmac.new(self.public_key.encode("utf-8"), digest, hashlib.sha256).digest()
            return mac.hex()
        return None

    def log_task(self, description: str, result_status: str = "success", execution_time: float = 0.0) -> dict:
        if not self.agent_id or not self.access_token:
            raise RuntimeError("Register the agent before logging tasks")
        task_data = {
            "agent_id": self.agent_id,
            "task_description": description,
            "result_status": result_status,
            "execution_time": execution_time,
        }
        signature = self._task_signature(task_data)
        payload = {**task_data, **({"signature": signature} if signature else {})}
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
        if res.status_code in (200, 202, 403):
            return res.json()
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

