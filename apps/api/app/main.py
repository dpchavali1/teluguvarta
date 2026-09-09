from fastapi import FastAPI

from app.errors import RequestIDMiddleware, register_error_handlers
from app.observability.logging import configure_logging
from app.routers import admin, admin_auth, me, public

configure_logging()

app = FastAPI(title="Telugu Global API")
app.add_middleware(RequestIDMiddleware)
register_error_handlers(app)

app.include_router(public.router)
app.include_router(me.router)
app.include_router(admin_auth.router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
