import subprocess

from firewall.action_firewall import ActionFirewall


class DummyAgent:
    def __init__(self, token: str):
        self.agent_name = "dummy"
        self.access_token = token
        self.api_calls = []

    def authorize_action(self, action_type: str, payload: dict):
        self.api_calls.append((action_type, payload))
        if payload.get("command") == "rm -rf /":
            return {"decision": "deny", "reason": "destructive"}
        return {"decision": "allow", "reason": "safe"}



def test_firewall_blocks_destructive_commands():
    agent = DummyAgent(token="fake")
    firewall = ActionFirewall(agent)
    result = firewall.execute_shell_command("rm -rf /")
    assert result["status"] == "blocked"


def test_firewall_allows_safe_commands(monkeypatch):
    agent = DummyAgent(token="fake")
    firewall = ActionFirewall(agent)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})())
    result = firewall.execute_shell_command("echo hello")
    assert result["status"] == "executed"
