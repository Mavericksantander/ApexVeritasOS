from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def register_bot(name: str = "test_bot") -> dict:
    payload = {
        "agent_name": name,
        "owner_id": "pytest",
        "capabilities": ["testing"],
    }
    response = client.post("/register_agent", json=payload)
    response.raise_for_status()
    return response.json()


def test_register_agent_produces_token():
    bot = register_bot("auth_bot")
    assert "access_token" in bot
    assert bot["token_type"] == "bearer"


def test_protected_route_requires_auth():
    response = client.get("/agents")
    assert response.status_code == 401


def test_access_with_token():
    bot = register_bot("auth_token")
    headers = {"Authorization": f"Bearer {bot['access_token']}"}
    response = client.get("/agents", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
