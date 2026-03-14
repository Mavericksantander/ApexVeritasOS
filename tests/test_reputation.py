from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_reputation_flow():
    payload = {
        "agent_name": "rep_bot",
        "owner_id": "pytest",
        "capabilities": ["reputation"],
    }
    response = client.post("/register_agent", json=payload)
    response.raise_for_status()
    data = response.json()
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    update_resp = client.post(
        "/update_reputation",
        headers=headers,
        json={"agent_id": data["agent_id"], "delta": 1.0, "reason": "test"},
    )
    assert update_resp.status_code == 200
    history_resp = client.get("/reputation/history", headers=headers)
    assert history_resp.status_code == 200
    assert isinstance(history_resp.json(), list)
