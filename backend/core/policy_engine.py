from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

import structlog
from sqlalchemy.orm import Session

from ..models import Policy

logger = structlog.get_logger()


def severity_label(severity: int) -> str:
    if severity >= 9:
        return "critical"
    if severity >= 7:
        return "high"
    if severity >= 4:
        return "medium"
    return "low"


def _matches(pattern: str, text: str) -> bool:
    pattern = (pattern or "").strip()
    if not pattern:
        return False
    # Regex mode: /.../ or re:...
    if (pattern.startswith("/") and pattern.endswith("/") and len(pattern) > 2) or pattern.lower().startswith("re:"):
        expr = pattern[1:-1] if pattern.startswith("/") else pattern[3:]
        try:
            return re.search(expr, text, flags=re.IGNORECASE) is not None
        except re.error:
            return False
    return pattern.lower() in text.lower()


def evaluate_policies(
    db: Session,
    action_type: str,
    payload: Dict[str, Any],
) -> Optional[Tuple[str, str, str]]:
    """Return (decision, reason, severity_label) if a policy matches, else None."""
    policies = db.query(Policy).order_by(Policy.severity.desc()).all()
    if not policies:
        return None

    target = ""
    if action_type == "execute_shell_command":
        target = str((payload or {}).get("command", ""))
    else:
        target = json.dumps(payload or {}, sort_keys=True, default=str)

    for policy in policies:
        if _matches(policy.pattern, target):
            action = (policy.action or "").strip().lower()
            if action == "require_approval":
                decision = "require_verification"
            elif action in {"deny", "allow"}:
                decision = action
            else:
                decision = "deny"
            reason = f"Policy '{policy.name}' matched"
            sev = severity_label(int(policy.severity or 5))
            logger.info(
                "policy.matched",
                policy=policy.name,
                decision=decision,
                severity=sev,
                action_type=action_type,
            )
            return decision, reason, sev
    return None

