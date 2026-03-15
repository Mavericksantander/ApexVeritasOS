# ApexVeritasOS (AVOS)

AVOS es una plataforma de gobernanza para agentes autónomos: identidad, autenticación JWT, logging de tareas, reputación y controles de seguridad (firewall + policies), con un dashboard HTML/JS y eventos SSE para demos.

![CI](https://github.com/Mavericksantander/fantastic-octo-potato/actions/workflows/ci.yml/badge.svg)

## Qué trae este repo
- **Backend**: FastAPI + SQLAlchemy 2.0 (`backend/`)
- **DB**: SQLite por defecto (`avos.db`), compatible con Postgres vía `DATABASE_URL`
- **Auth**: JWT (firmado con `SECRET_KEY`) + token de sesión temporal (`POST /auth/token`)
- **Migrations**: Alembic (`migrations/`)
- **SDK Python**: instalable como paquete (`avos_sdk/`) y compat legacy (`sdk/`)
- **Dashboard**: `dashboard/index.html` + `dashboard/app.js` (polling a `GET /dashboard/summary`)
- **Eventos**: SSE en `GET /events` (in-memory, single-process)
- **Logging**: `structlog`
- **Apex Registry**: directorio público de agentes verificados (`GET /registry/agents`) + attestations (`POST /registry/attestations`)
- **Apex Observatory**: observabilidad básica (`/observatory/activity`, `/observatory/graph`, `/observatory/trust_analytics`)

## Requisitos
- Python 3.9+

## Clonar el repo
```bash
git clone https://github.com/Mavericksantander/ApexVeritasOS.git
cd ApexVeritasOS/Avos
```

## Levantar el backend (local)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn backend.main:app --reload
```

- Docs: `http://127.0.0.1:8000/docs`
- Dashboard summary: `http://127.0.0.1:8000/dashboard/summary`

## Configuración (.env)
Puedes crear un `.env` (ver `backend/core/config.py`):
- `DATABASE_URL` (ej: `postgresql://user:pass@localhost/avos`)
- `SECRET_KEY` (JWT)
- `AVOS_RATE_LIMIT` / `AVOS_RATE_WINDOW`
- `DEBUG`, `ENVIRONMENT`, `CORS_ORIGINS`
- `REGISTRY_ISSUER_KEYS` (JSON string, para attestations HMAC en MVP)

Ejemplo:
```bash
REGISTRY_ISSUER_KEYS='{"ExampleCorp":"supersecret"}'
```

## Demo rápida (datos de prueba)
Con el backend corriendo:
```bash
AVOS_BASE_URL=http://127.0.0.1:8000 python3 -u scripts/simulate_agents.py
```

Para ver eventos en vivo:
```bash
curl -N http://127.0.0.1:8000/events
```

## SDK (Python)
### Instalar
Desde el repo (editable):
```bash
pip install -e .
```

Directo desde GitHub (sin clonar):
```bash
python3 -m pip install "git+https://github.com/Mavericksantander/ApexVeritasOS.git#subdirectory=Avos"
```

Distribución interna (wheel):
```bash
python3 -m pip install build
python3 -m build
python3 -m pip install dist/*.whl
```

Import recomendado:
```python
from avos_sdk import AVOSAgent
```

Compatibilidad (legacy):
```python
from sdk.avos_agent import AVOSAgent
```

### Ejemplo mínimo
```python
from avos_sdk import AVOSAgent

agent = AVOSAgent(
    agent_name="research_bot",
    owner_id="local",
    capabilities=["web_research"],
    base_url="http://127.0.0.1:8000",
)
agent.register_agent()
agent.fetch_token()
agent.send_heartbeat(status="active")
agent.log_task("web research", result_status="success", execution_time=0.2)
agent.authorize_action("execute_shell_command", {"command": "echo hello"})
```

## Adapters (OpenClaw / LangChain / CrewAI)
AVOS incluye wrappers livianos (sin dependencias forzadas) para traducir tool calls → `authorize_action` y resultados → `log_task`.

- Código: `avos_sdk/adapters/`
- Ejemplos: `scripts/examples/`

Notas:
- `capabilities` acepta `list[str]` (legacy) o `list[{name, version}]` (estructurado).
- `log_task` envía `signature` automáticamente (por defecto: HMAC-SHA256 usando el `public_key` devuelto al registrar).

## Onboarding externo (invite-protected)
Endpoint:
- `POST /external/register_agent`

Ejemplo:
```bash
curl -sS -X POST http://127.0.0.1:8000/external/register_agent \
  -H 'Content-Type: application/json' \
  -d '{"developer_id":"acme_inc","bot_name":"acme_scout","capabilities":["research"],"invite_code":"AVOS-OPEN-2026"}'
```

Los invite codes viven en `backend/routes/external_onboarding.py`.

## Endpoints clave
- Auth: `POST /auth/token`
- Identidad: `GET /agents/{agent_id}/identity` (JWT, solo self)
- Registro local: `POST /register_agent`

## Apex Registry
Directorio público de agentes verificados por AVOS (sin JWT):
- `GET /registry/agents?capability=<cap>&min_reputation=<n>&active_only=<bool>&include_attestations=<bool>`

Attestations (issuer-signed) para claims como `organization`, `model`, etc.:
- `POST /registry/attestations`

## Apex Observatory
Observabilidad operativa (sin JWT):
- `GET /observatory/activity`
- `GET /observatory/graph?since_minutes=60`
- `GET /observatory/trust_analytics`
- Heartbeat: `POST /agents/{agent_id}/heartbeat` (JWT, solo self)
- Activos: `GET /agents/active` (JWT)
- Directory: `GET /agents/public` (JWT)
- Search: `GET /agents/search?capability=<name>&min_reputation=<score>` (JWT)
- Tasks: `POST /log_task` y alias `POST /agent/{agent_id}/log_task` (JWT)
- Firewall decisioning: `POST /authorize_action` (JWT)
- Policies: `GET /policies` y `POST /policies` (JWT + capability `admin`)
- SSE: `GET /events`

## Tests
```bash
python3 -m pytest -q
python3 -m pytest -q --cov=backend
```

CI (GitHub Actions) corre tests + migraciones en cada push/PR. El umbral de coverage en CI está temporalmente en 60% mientras se agregan tests de `policies`, `a2a` y `constitution`.

## Migrations (Alembic)
Aplicar:
```bash
alembic upgrade head
```

Generar:
```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```
