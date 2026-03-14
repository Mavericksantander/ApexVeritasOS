import json
from typing import Any, Dict

from fastapi.responses import JSONResponse
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from ..core.security import verify_token
from ..database import SessionLocal
from ..models import AuthorizationLog
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
            decision, reason, severity = evaluate_action(payload.get("action_type", ""), payload.get("action_payload", {}))
            agent_id = self._extract_agent(payload, request)
            self._log_decision(agent_id, payload, decision, reason, severity)
            if decision != "allow":
                return JSONResponse(
                {"detail": reason, "decision": decision, "severity": severity},
                status_code=403 if decision == "deny" else 202,
            )
            request._receive = self._replay_body(body)
        return await call_next(request)

    def _log_decision(self, agent_id: str | None, payload: Dict[str, Any], decision: str, reason: str, severity: str) -> None:
        with SessionLocal() as db:
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

    def _extract_agent(self, payload: Dict[str, Any], request: Request) -> str | None:
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
