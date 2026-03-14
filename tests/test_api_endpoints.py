from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def get_auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_log_task_and_metrics():
    payload = {
        "agent_name": "api_bot",
        "owner_id": "pytest",
        "capabilities": ["api"],
    }
    response = client.post("/register_agent", json=payload)
    response.raise_for_status()
    data = response.json()
    headers = get_auth_headers(data["access_token"])
    log_resp = client.post(
        "/log_task",
        headers=headers,
        json={
            "agent_id": data["agent_id"],
            "task_description": "api-test",
            "result_status": "success",
            "execution_time": 0.5,
        },
    )
    assert log_resp.status_code == 200
    metrics_resp = client.get("/metrics/blocked_actions", headers=headers)
    assert metrics_resp.status_code == 200
    assert "blocked_actions_count" in metrics_resp.json()
