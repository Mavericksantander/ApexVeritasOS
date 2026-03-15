import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from pathlib import Path
from uuid import uuid4

#          /\\
#         /  \\
#        /    \\
#       /      \\
#      /  APEX  \\
#     / VERITAS  \\
#    /____________\\
# Be bold and mighty forces will come to your aid.

from .database import init_db
from .routes import agents as agent_routes
from .routes import authorization as auth_routes
from .routes import constitution as constitution_routes
from .routes import a2a as a2a_routes
from .routes import events as event_routes
from .routes import external_onboarding as onboarding_routes
from .routes import heartbeat as heartbeat_routes
from .routes import metrics as metrics_routes
from .routes import observatory as observatory_routes
from .routes import policies as policy_routes
from .routes import reputation as reputation_routes
from .routes import registry as registry_routes
from .routes import search as search_routes
from .routes import tasks as task_routes
from .routes import trust as trust_routes
from .core.config import settings
from .core.logging import bind_request, configure_logging, reset_context
from .core.rate_limiter import limiter
from .middleware.firewall_middleware import FirewallMiddleware

logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO)

logger = configure_logging()

app = FastAPI(title="ApexVeritasOS Governance API")

_DASHBOARD_DIR = Path(__file__).resolve().parents[1] / "dashboard"

if _DASHBOARD_DIR.exists():
    app.mount("/dashboard", StaticFiles(directory=str(_DASHBOARD_DIR), html=True), name="dashboard")


@app.get("/", include_in_schema=False)
def landing_page():
    # Keep one canonical landing: /dashboard/ (StaticFiles html=True serves dashboard/index.html).
    if _DASHBOARD_DIR.exists():
        return RedirectResponse(url="/dashboard/", status_code=307)
    return JSONResponse({"detail": "Dashboard directory not found. Try /docs."}, status_code=404)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(429, _rate_limit_exceeded_handler)
app.add_middleware(FirewallMiddleware)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = str(uuid4())
    bind_request(request_id=request_id)
    request.state.request_id = request_id
    logger.info("request.start", method=request.method, path=str(request.url.path))
    response = await call_next(request)
    logger.info("request.end", status_code=response.status_code)
    reset_context()
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning("http.error", status_code=exc.status_code, detail=exc.detail)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error("validation.error", errors=exc.errors())
    return JSONResponse({"detail": exc.errors()}, status_code=422)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version="0.1.0",
        description="Governance API for ApexVeritasOS",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

app.include_router(agent_routes.router)
app.include_router(task_routes.router)
app.include_router(trust_routes.router)
app.include_router(reputation_routes.router)
app.include_router(auth_routes.router)
app.include_router(onboarding_routes.router)
app.include_router(heartbeat_routes.router)
app.include_router(metrics_routes.router)
app.include_router(search_routes.router)
app.include_router(event_routes.router)
app.include_router(policy_routes.router)
app.include_router(constitution_routes.router)
app.include_router(a2a_routes.router)
app.include_router(registry_routes.router)
app.include_router(observatory_routes.router)

init_db()


@app.on_event("startup")
def on_startup():
    logging.info("AVOS database schemas initialized")
