"""Admin login (docs/tickets/T05.md). Deliberately its own router with no
`current_admin` dependency — logging in is how you obtain the token that
dependency checks.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import AdminPrincipal, current_admin, current_admin_for_enrollment
from app.db import get_db
from app.errors import APIError
from app.models import User
from app.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    MfaDisableRequest,
    MfaEnrollRequest,
    MfaSetupResponse,
    MfaStatusResponse,
)
from app.security import (
    create_admin_access_token,
    create_admin_enrollment_token,
    decrypt_mfa_secret,
    encrypt_mfa_secret,
    generate_mfa_secret,
    is_login_rate_limited,
    mfa_provisioning_uri,
    record_login_attempt,
    verify_mfa_code,
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

    mfa_enrolled = bool(user.mfa_secret)
    if mfa_enrolled:
        if not body.mfa_code:
            record_login_attempt(db, email, client_ip, success=False)
            raise APIError(401, "MFA_REQUIRED", "Enter your authenticator app code")
        if not verify_mfa_code(decrypt_mfa_secret(user.mfa_secret), body.mfa_code):
            record_login_attempt(db, email, client_ip, success=False)
            raise APIError(401, "INVALID_MFA_CODE", "Incorrect authenticator app code")

    record_login_attempt(db, email, client_ip, success=True)
    user.last_login_at = datetime.now(UTC)
    db.commit()

    # ADR-012: an account with no mfa_secret yet gets a restricted
    # enrollment-scope token, not a full session — it can only reach
    # /mfa/setup and /mfa/enroll (see current_admin_for_enrollment).
    if mfa_enrolled:
        access_token, expires_in = create_admin_access_token(user.id, user.email, user.role)
    else:
        access_token, expires_in = create_admin_enrollment_token(user.id, user.email, user.role)

    return AdminLoginResponse(
        access_token=access_token,
        expires_in=expires_in,
        role=user.role,
        mfa_enrollment_required=not mfa_enrolled,
    )


@router.get("/mfa")
def mfa_status(admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)) -> MfaStatusResponse:
    user = db.get(User, admin.user_id)
    return MfaStatusResponse(enabled=bool(user and user.mfa_secret))


@router.post("/mfa/setup")
def mfa_setup(admin: AdminPrincipal = Depends(current_admin_for_enrollment)) -> MfaSetupResponse:
    # Not persisted here — see the MFA note above app/security.py's helpers.
    # An admin can call this repeatedly to get a fresh secret; only a
    # completed /mfa/enroll ever changes stored state.
    secret = generate_mfa_secret()
    return MfaSetupResponse(secret=secret, otpauth_url=mfa_provisioning_uri(secret, admin.email))


@router.post("/mfa/enroll")
def mfa_enroll(
    body: MfaEnrollRequest,
    admin: AdminPrincipal = Depends(current_admin_for_enrollment),
    db: Session = Depends(get_db),
) -> MfaStatusResponse:
    if not verify_mfa_code(body.secret, body.code):
        raise APIError(401, "INVALID_MFA_CODE", "Incorrect authenticator app code")
    user = db.get(User, admin.user_id)
    if user is None:
        raise APIError(404, "NOT_FOUND", "Admin user not found")
    user.mfa_secret = encrypt_mfa_secret(body.secret)
    db.commit()
    return MfaStatusResponse(enabled=True)


@router.delete("/mfa")
def mfa_disable(
    body: MfaDisableRequest, admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)
) -> MfaStatusResponse:
    user = db.get(User, admin.user_id)
    if user is None or not user.mfa_secret:
        raise APIError(409, "MFA_NOT_ENABLED", "MFA is not enabled on this account")
    if not verify_mfa_code(decrypt_mfa_secret(user.mfa_secret), body.code):
        raise APIError(401, "INVALID_MFA_CODE", "Incorrect authenticator app code")
    user.mfa_secret = None
    db.commit()
    return MfaStatusResponse(enabled=False)
