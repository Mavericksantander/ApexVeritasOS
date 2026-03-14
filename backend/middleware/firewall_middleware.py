import json
from typing import Any, Dict, Optional

from fastapi.responses import JSONResponse
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from ..core.security import verify_token
from ..database import SessionLocal
from ..models import AuthorizationLog
from ..core.policy_engine import evaluate_policies
from firewall.action_firewall import evaluate_action

BLOCKED_PATH = "/authorize_action"


class FirewallMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        payload = None
        if request.method.upper() == "POST" and request.url.path == BLOCKED_PATH:
            body = await request.body()
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
            except json.JSONDecodeError:
                payload = {}
            agent_id = self._extract_agent(payload, request)
            with SessionLocal() as db:
                policy_result = evaluate_policies(
                    db,
                    payload.get("action_type", ""),
                    payload.get("action_payload", {}) or {},
                )
                if policy_result:
                    decision, reason, severity = policy_result
                else:
                    decision, reason, severity = evaluate_action(
                        payload.get("action_type", ""),
                        payload.get("action_payload", {}) or {},
                    )
                log = AuthorizationLog(
                    agent_id=agent_id or "unknown",
                    action_type=payload.get("action_type", ""),
                    payload=json.dumps(payload.get("action_payload", {})),
                    decision=decision,
                    reason=reason,
                    blocked_reason=reason if decision != "allow" else None,
                    severity=severity,
                )
                db.add(log)
                db.commit()

                if decision != "allow":
                    return JSONResponse(
                        {"detail": reason, "decision": decision, "severity": severity},
                        status_code=403 if decision == "deny" else 202,
                    )
            request._receive = self._replay_body(body)
        return await call_next(request)

    def _extract_agent(self, payload: Dict[str, Any], request: Request) -> Optional[str]:
        token = None
        authorization = request.headers.get("authorization")
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization.split()[1]
        if not token and payload.get("agent_id"):
            return payload.get("agent_id")
        if token:
            try:
                data = verify_token(token)
                return data.get("agent_id")
            except JWTError:
                return None
        return None

    def _replay_body(self, body: bytes):
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        return receive
