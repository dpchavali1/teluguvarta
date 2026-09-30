import os

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.ai.budget import require_budget_config
from app.db import _engine_for
from app.errors import RequestIDMiddleware, register_error_handlers
from app.observability.logging import configure_logging, get_logger
from app.routers import admin, admin_auth, me, public

configure_logging()
logger = get_logger(__name__)
require_budget_config()

app = FastAPI(title="TTE — The Telugu Edit API")

# apps/web and apps/admin call this API directly from the browser (no
# server-side proxy) using a Bearer token, never cookies — so no origin
# needs `allow_credentials`. Without this, every client-side fetch (admin
# login, web analytics events, web onboarding's /v1/config) is silently
# blocked by the browser's CORS preflight, even though curl/pytest/jsdom
# checks never exercise real CORS and so never catch it.
_cors_origins = [o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestIDMiddleware)
register_error_handlers(app)

app.include_router(public.router)
app.include_router(me.router)
app.include_router(admin_auth.router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def ready(response: Response) -> dict[str, str]:
    """Review 2026-09-29 #9: readiness, unlike `/health`, fails (503) when the
    API can't reach Postgres. Used by the deploy health gate, the compose
    healthcheck and `infra/deploy/monitor.sh`."""
    try:
        with _engine_for(os.environ["DATABASE_URL"]).connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - any failure means not ready
        logger.warning("readiness check failed: %s", exc)
        response.status_code = 503
        return {"status": "unavailable", "db": "error"}
    return {"status": "ok", "db": "ok"}
