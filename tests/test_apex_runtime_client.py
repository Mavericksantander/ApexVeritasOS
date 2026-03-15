from __future__ import annotations

from fastapi.testclient import TestClient

from apex_runtime.client import ApexRuntimeClient
from apex_runtime.main import app


def test_http_client_authorize_action_testclient():
    hc = TestClient(app)
    client = ApexRuntimeClient(httpx_client=hc)
    res = client.authorize_action(
        {"public_key": "pk-test", "created_at": "2026-03-15T00:00:00Z"},
        "execute_shell",
        "rm -rf /",
    )
    assert res["decision"] == "DENY"
    assert res["avid"].startswith("AVID-")
