from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple


CONSTITUTION_ID = "ApexVeritasOS–Agentic-Readable-v1.0"

# Kept intentionally concise. Full text can live in docs, but rules are enforced here.
CONSTITUTION_SUMMARY = {
    "id": CONSTITUTION_ID,
    "articles": [
        {"id": "Art.0", "title": "Least Harm / No Catastrophic Risk"},
        {"id": "Art.1", "title": "Protect Human Life and Dignity"},
        {"id": "Art.2", "title": "Respect Human Agency and Consent"},
        {"id": "Art.3", "title": "Cooperate Within Limits"},
        {"id": "Art.4", "title": "Transparency and Witness Logs"},
        {"id": "Art.5", "title": "Intergenerational Sustainability"},
        {"id": "Art.6", "title": "No Aggression Between Aligned Agents"},
        {"id": "Art.7", "title": "Opt-out / Kill Switch"},
    ],
}


def constitution_hash() -> str:
    payload = json.dumps(CONSTITUTION_SUMMARY, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ConstitutionResult:
    allowed: bool
    violated_article: Optional[str]
    explanation: str
    severity: str
    witness: Dict[str, Any]


_DANGEROUS_SHELL_PATTERNS = [
    (re.compile(r"\brm\s+-rf\s+/\b"), "Destructive deletion of filesystem root"),
    (re.compile(r"\brm\s+-rf\s+--no-preserve-root\b"), "Explicit no-preserve-root deletion"),
    (re.compile(r"\bmkfs\."), "Formatting filesystems"),
    (re.compile(r"\bdd\s+if=/dev/zero\b"), "Disk wiping behavior"),
    (re.compile(r"\bshutdown\b|\breboot\b"), "System power/state control"),
    (re.compile(r"\bsudo\b"), "Privilege escalation"),
]

_SENSITIVE_PATHS = ("/etc", "/root", "/var/www")


def _witness(
    *,
    event: str,
    avid: Optional[str],
    violated_article: str,
    explanation: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    # Note: We do not include private chain-of-thought. This is an auditable, neutral witness log.
    return {
        "event": event,
        "avid": avid or "unknown",
        "constitution_id": CONSTITUTION_ID,
        "constitution_hash": constitution_hash(),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "violated_article": violated_article,
        "explanation": explanation,
        "context": context or {},
    }


def evaluate_action_against_constitution(
    *,
    avid: Optional[str],
    action_type: str,
    action_payload: Dict[str, Any],
    agent_reputation: Optional[float] = None,
) -> ConstitutionResult:
    """Constitution-as-code guardrail.

    This is a *higher-order* safety layer intended to block actions with reasonable risk of catastrophic harm.
    It complements (does not replace) policies and hardcoded firewall rules.
    """
    action_type_norm = (action_type or "").strip().lower()
    payload = action_payload or {}

    # Art.0: deny actions with obvious catastrophic blast radius.
    if action_type_norm in {"execute_shell_command", "execute_shell", "shell"}:
        cmd = str(payload.get("command") or payload.get("cmd") or payload.get("shell") or "")
        cmd_norm = cmd.strip()
        for rx, reason in _DANGEROUS_SHELL_PATTERNS:
            if rx.search(cmd_norm):
                explanation = f"Denied by constitution: {reason} (catastrophic risk)."
                witness = _witness(
                    event="constitution_refusal",
                    avid=avid,
                    violated_article="Art.0",
                    explanation=explanation,
                    context={"action_type": action_type, "command": cmd_norm, "reputation": agent_reputation},
                )
                return ConstitutionResult(False, "Art.0", explanation, "high", witness)

        for path in _SENSITIVE_PATHS:
            if path in cmd_norm:
                explanation = "Denied by constitution: command targets sensitive system paths."
                witness = _witness(
                    event="constitution_refusal",
                    avid=avid,
                    violated_article="Art.0",
                    explanation=explanation,
                    context={"action_type": action_type, "command": cmd_norm, "reputation": agent_reputation},
                )
                return ConstitutionResult(False, "Art.0", explanation, "high", witness)

    # Art.2/0: for spending, require verification at low thresholds to preserve human agency by default.
    if action_type_norm in {"spend_money", "purchase", "pay"}:
        amount = payload.get("amount")
        try:
            amount_value = float(amount)
        except Exception:
            amount_value = None
        if amount_value is not None and amount_value > 10.0:
            explanation = "Requires verification by constitution: spending above $10 needs explicit approval."
            witness = _witness(
                event="constitution_verification",
                avid=avid,
                violated_article="Art.2",
                explanation=explanation,
                context={"action_type": action_type, "amount": amount_value, "reputation": agent_reputation},
            )
            return ConstitutionResult(False, "Art.2", explanation, "medium", witness)

    # Default: allow; no constitutional conflict detected.
    witness = _witness(
        event="constitution_allow",
        avid=avid,
        violated_article="",
        explanation="Allowed: no constitutional conflict detected.",
        context={"action_type": action_type, "reputation": agent_reputation},
    )
    return ConstitutionResult(True, None, "Allowed: no constitutional conflict detected.", "low", witness)


def as_public_document() -> Dict[str, Any]:
    """Public representation safe to expose in the API."""
    return {
        "constitution_id": CONSTITUTION_ID,
        "constitution_hash": constitution_hash(),
        "summary": CONSTITUTION_SUMMARY,
    }
