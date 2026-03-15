from __future__ import annotations

from fastapi.testclient import TestClient

from apex_runtime.main import app


def test_authorize_action_endpoint_default_policy(tmp_path, monkeypatch):
    # Ensure audit log writes to a temp file.
    monkeypatch.setenv("APEX_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))

    client = TestClient(app)
    res = client.post(
        "/authorize_action",
        json={
            "agent_ctx": {"public_key": "pk-test", "created_at": "2026-03-15T00:00:00Z"},
            "action_type": "execute_shell",
            "action_payload": "rm -rf /",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] == "DENY"
    assert data["avid"].startswith("AVID-")

