"""Admin login (docs/tickets/T05.md). Deliberately its own router with no
`current_admin` dependency — logging in is how you obtain the token that
dependency checks.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import APIError
from app.models import User
from app.schemas import AdminLoginRequest, AdminLoginResponse
from app.security import (
    create_admin_access_token,
    is_login_rate_limited,
    record_login_attempt,
    verify_password,
)

router = APIRouter(prefix="/v1/admin/auth", tags=["admin-auth"])


@router.post("/login")
def login(body: AdminLoginRequest, request: Request, db: Session = Depends(get_db)) -> AdminLoginResponse:
    email = body.email.strip().lower()
    client_ip = request.client.host if request.client else None

    if is_login_rate_limited(db, email):
        raise APIError(429, "RATE_LIMITED", "Too many login attempts — try again later")

    user = db.scalar(
        select(User).where(User.email == email, User.role.is_not(None), User.deleted_at.is_(None))
    )
    if user is None or not user.password_hash or not verify_password(body.password, user.password_hash):
        record_login_attempt(db, email, client_ip, success=False)
        raise APIError(401, "INVALID_CREDENTIALS", "Incorrect email or password")

    record_login_attempt(db, email, client_ip, success=True)
    user.last_login_at = datetime.now(UTC)
    db.commit()

    access_token, expires_in = create_admin_access_token(user.id, user.email, user.role)
    return AdminLoginResponse(access_token=access_token, expires_in=expires_in, role=user.role)
