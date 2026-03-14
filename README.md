# ApexVeritasOS (AVOS) MVP

Plataforma de gobernanza para agentes autónomos: identidad, autenticación por JWT, logging de tareas, reputación y controles de seguridad (firewall/policies), con un dashboard HTML/JS simple.

## Stack
- **Backend**: FastAPI + SQLAlchemy 2.0
- **DB**: SQLite por defecto (`avos.db`), compatible con Postgres vía `DATABASE_URL`
- **Auth**: JWT (firmado con `SECRET_KEY`) + token de sesión temporal via `/auth/token`
- **Migrations**: Alembic (`migrations/`)
- **SDK**: `sdk/avos_agent.py` (Python)
- **Dashboard**: `dashboard/index.html` + `dashboard/app.js` (vanilla, polling a `/dashboard/summary`, opcional SSE)
- **Logging**: `structlog`

## Quick start (local)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Backend en `http://127.0.0.1:8000`.

## Variables de entorno
Puedes crear un `.env` (ver `backend/core/config.py`):
- `DATABASE_URL` (ej: `postgresql://user:pass@localhost/avos`)
- `SECRET_KEY` (JWT)
- `AVOS_RATE_LIMIT` / `AVOS_RATE_WINDOW`
- `DEBUG`, `ENVIRONMENT`, `CORS_ORIGINS`

## SDK (Python)
### Instalación (pip)
Si quieres que otros devs lo instalen desde su terminal como un paquete:

- **Desde este repo (editable)**:
```bash
cd /Users/josesantander/avos/Avos
source .venv/bin/activate
pip install -e .
```

- **Build + wheel** (para distribuir internamente):
```bash
cd /Users/josesantander/avos/Avos
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

Ejemplo mínimo:
```python
from sdk.avos_agent import AVOSAgent

agent = AVOSAgent("research_bot", owner_id="local", capabilities=["web_research", {"name": "admin"}])
agent.register_agent()     # obtiene agent_id + public_key (secreto) + token
agent.fetch_token()        # (recomendado) emite token temporal /auth/token

agent.send_heartbeat(model="gpt", version="1.0")
agent.log_task("web research", result_status="success", execution_time=2.3)
agent.authorize_action("execute_shell_command", {"command": "ls -la"})
```

Notas:
- `capabilities` acepta **legacy** `list[str]` o **estructurado** `list[{name, version}]`.
- `log_task` envía `signature` automáticamente (por defecto: HMAC-SHA256 usando `public_key` como secreto).

## Auth: token temporal (JWT)
El token recomendado es el de sesión temporal:
- `POST /auth/token`
  - Body: `{"agent_id": "...", "public_key": "...", "expires_in": 3600}`
  - Respuesta: `{"access_token": "...", "expires_in": 3600}`

Todas las rutas protegidas aceptan `Authorization: Bearer <access_token>`.

## Identidad verificable (MVP)
- `GET /agents/{agent_id}/identity` (JWT requerido, solo “self”)

Respuesta:
```json
{
  "agent_id": "…",
  "developer_id": "…",
  "public_key": "…",
  "capabilities": ["…"],
  "created_at": "2026-03-14T00:00:00Z",
  "reputation": 1.5,
  "verified": true
}
```

## Registro y discovery
- `POST /register_agent` (dev/local)
- `POST /external/register_agent` (invite-protected)
- `GET /agents/public` (requiere JWT)
- `GET /agents/search?capability=<cap>&min_reputation=<score>` (requiere JWT; filtra por `capability.name`)
- `GET /agents/active` (requiere JWT; `last_heartbeat_at` en últimos 5 min)

## Heartbeat
- `POST /agents/{agent_id}/heartbeat` (JWT requerido, solo “self”)

## Logging de tareas, reputación y firma
Endpoints:
- `POST /log_task` (JWT requerido)
- `POST /agent/{agent_id}/log_task` (alias compatible) (JWT requerido)

Body (nuevo, compatible):
```json
{
  "agent_id": "...",
  "task_description": "…",
  "result_status": "success",
  "execution_time": 0.5,
  "signature": "… (opcional)"
}
```

Si `signature` está presente y es inválida:
- se rechaza el log (`403`)
- se aplica penalización de reputación (delta `-1.0`)

## SSE (eventos en tiempo real)
- `GET /events` (Server-Sent Events)

Eventos emitidos (in-memory, single-process):
- `agent_registered`
- `task_completed`
- `reputation_updated`

Ejemplo (browser):
```js
const es = new EventSource("http://127.0.0.1:8000/events");
es.addEventListener("reputation_updated", (ev) => console.log(JSON.parse(ev.data)));
```

## Policy engine (configurable)
Tabla `policies` + evaluación previa al firewall hardcodeado.

Endpoints:
- `GET /policies` (JWT requerido)
- `POST /policies` (JWT requerido + capability `admin`)

Body ejemplo:
```json
{"name":"deny_rm_rf","pattern":"rm -rf","action":"deny","severity":10}
```

`pattern` soporta match simple (substring) o regex (`/expr/` o `re:expr`).

## Firewall /authorize_action
- `POST /authorize_action` (JWT requerido)

La decisión se calcula así:
1) Policies dinámicas (DB) si hay match  
2) Reglas hardcodeadas (`firewall/action_firewall.py`) si no hay match  

Todas las decisiones se loguean en `authorization_logs`.

## Dashboard
Abrir `dashboard/index.html` en un browser (o servirlo estático). Hace polling a:
- `GET /dashboard/summary`

## Tests
```bash
pytest --cov=backend
```

## Migrations (Alembic)
Para aplicar migrations:
```bash
alembic upgrade head
```

Para generar nuevas:
```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```
