from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .audit import HashChainAuditLog
from .identity import generate_avid


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


@dataclass(frozen=True)
class DecisionResult:
    decision: Decision
    reason: str

    def as_dict(self) -> Dict[str, Any]:
        return {"decision": self.decision.value, "reason": self.reason}


def _parse_minimal_yaml_rules(text: str) -> Dict[str, Any]:
    """Parse a tiny YAML subset for our policies.yaml.

    Supported:
    - Top-level mapping keys with scalar values (strings/bools)
    - `rules:` key with a list of rule mappings, each containing scalar values
    - Indentation-based structure with `-` list items

    This is intentionally minimal to avoid external YAML dependencies.
    """
    lines = [ln.rstrip("\n") for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    out: Dict[str, Any] = {}
    rules: List[Dict[str, Any]] = []
    out["rules"] = rules

    def parse_scalar(v: str) -> Any:
        v = v.strip()
        if v.lower() in {"true", "false"}:
            return v.lower() == "true"
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            return v[1:-1]
        return v

    i = 0
    in_rules = False
    current_rule: Optional[Dict[str, Any]] = None
    while i < len(lines):
        ln = lines[i]
        stripped = ln.lstrip(" ")
        indent = len(ln) - len(stripped)
        if indent == 0 and stripped.endswith(":"):
            key = stripped[:-1].strip()
            in_rules = key == "rules"
            current_rule = None
            i += 1
            continue
        if not in_rules:
            if ":" in stripped:
                k, v = stripped.split(":", 1)
                out[k.strip()] = parse_scalar(v)
            i += 1
            continue

        # in rules
        if stripped.startswith("- "):
            current_rule = {}
            rules.append(current_rule)
            rest = stripped[2:].strip()
            if rest and ":" in rest:
                k, v = rest.split(":", 1)
                current_rule[k.strip()] = parse_scalar(v)
            i += 1
            continue

        if current_rule is not None and ":" in stripped:
            k, v = stripped.split(":", 1)
            key = k.strip()
            val = v.strip()
            if val == "":
                # List block (subset):
                #   deny_if:
                #     - "a"
                #     - "b"
                items: List[Any] = []
                i += 1
                while i < len(lines):
                    ln2 = lines[i]
                    stripped2 = ln2.lstrip(" ")
                    indent2 = len(ln2) - len(stripped2)
                    if indent2 <= indent:
                        break
                    if stripped2.startswith("- "):
                        items.append(parse_scalar(stripped2[2:]))
                    i += 1
                current_rule[key] = items
                continue
            current_rule[key] = parse_scalar(val)
        i += 1

    return out


def load_policies(policy_file: str | Path) -> Dict[str, Any]:
    text = Path(policy_file).read_text(encoding="utf-8")
    return _parse_minimal_yaml_rules(text)


def _match_rule(rule: Dict[str, Any], action_type: str) -> bool:
    return str(rule.get("action_type", "")).strip() == action_type


def _payload_text(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    return str(payload)


def _safe_paths_from_ctx(agent_ctx: Dict[str, Any]) -> List[str]:
    safe_paths = agent_ctx.get("safe_paths")
    if isinstance(safe_paths, list):
        return [str(p) for p in safe_paths]
    return []


def authorize_action(
    agent_ctx: Dict[str, Any],
    action_type: str,
    action_payload: Any,
    *,
    policy_file: str | Path = Path(__file__).with_name("policies.yaml"),
    audit_log_path: str | Path = "audit.log",
) -> Dict[str, Any]:
    """Authorize an agent action and record an audit entry.

    Returns a dict:
      { "decision": "ALLOW|DENY|REQUIRE_APPROVAL", "reason": str, "avid": str }
    """
    ctx = dict(agent_ctx or {})
    avid = str(ctx.get("avid") or "") or generate_avid(ctx)

    policies = load_policies(policy_file)
    rules = policies.get("rules") or []
    rules = rules if isinstance(rules, list) else []

    decision = Decision.ALLOW
    reason = "Allowed by default"

    payload_text = _payload_text(action_payload).lower()
    for rule in rules:
        if not isinstance(rule, dict) or not _match_rule(rule, action_type):
            continue

        if rule.get("require_approval") is True:
            decision = Decision.REQUIRE_APPROVAL
            reason = "Policy requires approval"
            break

        deny_if = rule.get("deny_if")
        if isinstance(deny_if, str):
            deny_items = [deny_if]
        elif isinstance(deny_if, list):
            deny_items = [str(x) for x in deny_if if str(x).strip()]
        else:
            deny_items = []
        for item in deny_items:
            if item.lower() in payload_text:
                decision = Decision.DENY
                reason = f"Denied by policy: matched '{item}'"
                break
        if decision == Decision.DENY:
            break

        allow_if = rule.get("allow_if")
        if allow_if == "safe_paths":
            # Expect payload to contain a file path (dict with key "path" or direct string).
            if isinstance(action_payload, dict):
                path = str(action_payload.get("path", "") or "")
            else:
                path = str(action_payload or "")
            safe_paths = _safe_paths_from_ctx(ctx)
            if any(path.startswith(prefix) for prefix in safe_paths):
                decision = Decision.ALLOW
                reason = "Allowed by policy: safe_paths"
            else:
                decision = Decision.DENY
                reason = "Denied by policy: unsafe path"
            break

        # Regex match support (optional) without needing a richer DSL.
        deny_regex = rule.get("deny_regex")
        if isinstance(deny_regex, str):
            regexes = [deny_regex]
        elif isinstance(deny_regex, list):
            regexes = [str(x) for x in deny_regex if str(x).strip()]
        else:
            regexes = []
        for rx in regexes:
            if re.search(rx, payload_text):
                decision = Decision.DENY
                reason = "Denied by policy: deny_regex"
                break
        if decision == Decision.DENY:
            break

    audit = HashChainAuditLog(audit_log_path)
    audit.append(
        avid=avid,
        action_type=action_type,
        decision=decision.value,
        reason=reason,
    )

    return {"decision": decision.value, "reason": reason, "avid": avid}
