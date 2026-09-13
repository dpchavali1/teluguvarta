import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.errors import RequestIDMiddleware, register_error_handlers
from app.observability.logging import configure_logging
from app.routers import admin, admin_auth, me, public

configure_logging()

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
