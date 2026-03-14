from typing import Any, Dict, Tuple

BLOCKED_PATTERNS = ["rm -rf", "sudo", "/etc", "/root", "/var/www"]
HIGH_RISK_COMMANDS = ["chmod", "chown", "dd", "mkfs"]
HIGH_SPEND_THRESHOLD = 10.0


def evaluate_action(action_type: str, payload: Dict[str, Any]) -> Tuple[str, str, str]:
    payload = payload or {}
    decision = "allow"
    reason = "Action classified as safe"
    severity = "low"

    if action_type == "execute_shell_command":
        command = str(payload.get("command", "")).lower()
        if any(pattern in command for pattern in BLOCKED_PATTERNS):
            return "deny", "Destructive command detected", "critical"
        if any(pattern in command for pattern in HIGH_RISK_COMMANDS):
            return "require_verification", "Privileged command needs approval", "high"
        if payload.get("requires_root"):
            return "require_verification", "Root-level command needs extra confirmation", "high"
    elif action_type == "spend_money":
        amount = float(payload.get("amount", 0))
        if amount > HIGH_SPEND_THRESHOLD:
            return "require_verification", "Spending exceeds allowed threshold", "high"
        severity = "medium"
    elif action_type == "modify_file":
        target = payload.get("path", "")
        if target.startswith("/etc") or target.startswith("/usr/bin"):
            return "deny", "Changing critical system files is blocked", "critical"
    elif action_type == "call_external_api":
        domain = payload.get("domain", "")
        if not domain or domain.endswith(".internal"):
            return "deny", "External API target is not approved", "critical"
    return decision, reason, severity


class ActionFirewall:
    def __init__(self, agent: Any):
        self.agent = agent

    def execute_shell_command(self, command: str) -> Dict[str, Any]:
        decision, reason, severity = evaluate_action("execute_shell_command", {"command": command})
        if decision != "allow":
            return {"status": "blocked", "decision": decision, "reason": reason, "severity": severity}
        result = self._safe_run(command)
        return {"status": "executed", "severity": severity, **result}

    def _safe_run(self, command: str) -> Dict[str, Any]:
        import subprocess

        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
