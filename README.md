<<<<<<< HEAD
# fantastic-octo-potato
=======
# ApexVeritasOS (AVOS) MVP

A governance platform for autonomous AI agents that provides identity, logging, and safety controls while being easy to spin up locally.

## Stack
- FastAPI backend with SQLite (craft to swap with PostgreSQL via `DATABASE_URL`).
- Python Agent SDK for interacting with the platform.
- Firewall middleware to intercept shell actions.
- Simple HTML/JS dashboard querying FastAPI.

## Quick start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```
The server launches on `http://127.0.0.1:8000` and creates `avos.db` (SQLite).

## Registering a test agent
1. Use the SDK to register an agent and receive a JWT for future calls:
    ```python
    from sdk.avos_agent import AVOSAgent

    agent = AVOSAgent("research_bot", capabilities=["web_research", "data_ingest"])
    agent.register_agent()
    print(agent.access_token)
    ```
2. Store the returned `access_token` and send it as `Authorization: Bearer <token>` on subsequent requests (the `public_key` is only returned for audit).

## Logging a task & reputation
```python
agent.log_task("web research", result_status="success", execution_time=3.2)
```
Every successful task bumps the reputation score by `0.5`, failures subtract `1.0`, and the updated score is returned.

## Authorization testing
Ask the platform whether an agent may perform a risky action using the JWT token:
```python
decision = agent.authorize_action("execute_shell_command", {"command": "rm -rf /tmp/test"})
print(decision)
```
The API enforces rules such as blocking destructive shell commands, denying edits under `/etc`, requiring verification for large spending, and logging every authorization attempt.

## Action firewall demo
Incorporate the firewall module to block dangerous shell requests before they reach your agent framework:
```python
from firewall.action_firewall import ActionFirewall
firewall = ActionFirewall(agent)
firewall.execute_shell_command("rm -rf /tmp/sensitive")
```
If the backend denies the action, the firewall returns `status: blocked` and the command is not executed.

## Dashboard
Open `dashboard/index.html` in a browser (or serve it via any static server). It visualizes:
- Registered agents with reputation
- Recent tasks
- Reputation snapshots
- Blocked actions logged by the authorization API

It fetches data from `GET /dashboard/summary`, which aggregates agents, tasks, and denied authorizations.

## Environment overrides
Copy `.env.example` to `.env` and set the secrets/overrides you need:
- `DATABASE_URL` to point to PostgreSQL (e.g., `postgresql://user:pass@localhost/avos`).
- `AVOS_RATE_LIMIT`/`AVOS_RATE_WINDOW` for rate-limiting.
- `SECRET_KEY` for future JWT usage (required by `backend/core/config.py`).
- `DEBUG`, `ENVIRONMENT`, and `CORS_ORIGINS` as needed for your deployment.

## Additional APIs
- **Heartbeat:** `POST /agents/{agent_id}/heartbeat` lets agents report their status and metadata.
- **Public directory:** `GET /agents/public` lists agents with reputation and capabilities for discovery.
- **Search:** `GET /agents/search?capability=<cap>&min_reputation=<score>` filters agents by capability and score.
- **Metrics:** `GET /metrics/blocked_actions` returns how many actions have been denied to date.

## OpenClaw integration & exposure
1. Run the API on all interfaces and expose it externally:
   ```bash
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ngrok http 8000  # optional: share the generated https://*.ngrok.io URL with OpenClaw
   ```
2. OpenClaw bots call `/external/register_agent` to onboard. Include `developer_id`, `bot_name`, `capabilities`, and the shared `invite_code` (e.g. `AVOS-OPEN-2026`).
3. Store the returned `agent_id`/`access_token` and send it as `Authorization: Bearer <token>` for every follow-up request.

### OpenClaw sample payloads
```jsonc
// 1. Register the agent
POST /external/register_agent
Content-Type: application/json

{
  "developer_id": "openclaw_team",
  "bot_name": "openclaw_scout",
  "capabilities": ["web_scraping", "decisioning"],
  "invite_code": "AVOS-OPEN-2026"
}

// 2. Log a completed task after registration
POST /agent/{agent_id}/log_task
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "agent_id": "<agent_id>",
  "task_description": "Harvest market data",
  "result_status": "success",
  "execution_time": 2.8
}

// 3. Request authorization before a risky command
POST /authorize_action
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "agent_id": "<agent_id>",
  "action_type": "execute_shell_command",
  "action_payload": {"command": "rm -rf /tmp/reports"}
}
```
OpenClaw skill/webhook should send these requests sequentially, honoring `Authorization: Bearer <access_token>`.

## Simulation helper
Run `scripts/simulate_agents.py` to register a few agents, push heartbeat updates, log tasks, and trigger blocked shell commands so you can see the dashboard and logs populate quickly.

## Containerization
Build the Docker image:
```bash
docker build -t avos-app .
```
Run it:
```bash
docker run --env-file .env --publish 8000:8000 avos-app
```
Or start the stack with Compose (includes PostgreSQL):
```bash
docker compose up --build
```

## Observabilidad
Los logs ahora se formatean con `structlog` y cada petición recibe `request_id`, `agent_id`, `reputation_delta` y contexto de seguridad. Las excepciones HTTP/Validation quedan anotadas con nivel warning/error.

## Firewall middleware
Las solicitudes a `/authorize_action` ahora pasan por un middleware que bloquea comandos con `rm -rf`, `sudo` o accesos a `/etc`, `/root`, `/var/www`, registra la decisión con nivel de severidad y exige verificación adicional para gastos mayores a $10.

## Tests
Run the test suite and collect coverage:
```bash
pytest --cov=backend
```

## Migrations
The project now runs with SQLAlchemy 2.0 and Alembic. After installing requirements and copying `.env.example` to `.env`, initialize the schema with:
```bash
alembic upgrade head
```
To capture schema changes, run `alembic revision --autogenerate -m "describe change"` before upgrading. The local `migrations/` directory is configured to read `DATABASE_URL` from your `.env`, so the same commands work against SQLite and PostgreSQL.

## Next steps
- Wire the firewall into OpenClaw or other agent runners (use `ActionFirewall` in your execution pipeline).
- Swap SQLite for PostgreSQL in production by setting `DATABASE_URL` and running migrations.
- Extend the dashboard with authentication and richer analytics.
