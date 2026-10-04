"""Admin login (docs/tickets/T05.md) and sessions (ADR-028). Login has no
`current_admin` dependency — logging in is how you obtain the session cookie
that dependency checks.
"""

from datetime import UTC, datetime
from typing import Literal, cast

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin_sessions import (
    COOKIE_NAME,
    SCOPE_FULL,
    SCOPE_MFA_ENROLLMENT,
    clear_session_cookie,
    create_session,
    idle_expires_at,
    live_sessions_for_user,
    require_csrf_header,
    resolve_session,
    revoke,
    revoke_all_for_user,
    set_session_cookie,
)
from app.auth import AdminPrincipal, current_admin, current_admin_for_enrollment
from app.db import get_db
from app.errors import APIError
from app.models import User
from app.schemas import (
    AdminCurrentSessionOut,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminSessionListOut,
    AdminSessionOut,
    MfaDisableRequest,
    MfaEnrollRequest,
    MfaSetupResponse,
    MfaStatusResponse,
)
from app.security import (
    decrypt_mfa_secret,
    encrypt_mfa_secret,
    generate_mfa_secret,
    is_login_ip_rate_limited,
    is_login_rate_limited,
    mfa_provisioning_uri,
    record_login_attempt,
    verify_mfa_code,
    verify_password,
)

router = APIRouter(prefix="/v1/admin/auth", tags=["admin-auth"])


@router.post("/login")
def login(
    body: AdminLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> AdminLoginResponse:
    # Login CSRF: a cross-site form can't sign the browser into another account.
    require_csrf_header(request)
    email = body.email.strip().lower()
    client_ip = request.client.host if request.client else None

    if is_login_rate_limited(db, email) or is_login_ip_rate_limited(db, client_ip):
        raise APIError(429, "RATE_LIMITED", "Too many login attempts — try again later")

    user = db.scalar(
        select(User).where(User.email == email, User.role.is_not(None), User.deleted_at.is_(None))
    )
    if user is None or user.role not in ("EDITOR", "ADMIN") or not user.password_hash or not verify_password(body.password, user.password_hash):
        record_login_attempt(db, email, client_ip, success=False)
        raise APIError(401, "INVALID_CREDENTIALS", "Incorrect email or password")

    mfa_enrolled = bool(user.mfa_secret)
    if mfa_enrolled:
        if not body.mfa_code:
            record_login_attempt(db, email, client_ip, success=False)
            raise APIError(401, "MFA_REQUIRED", "Enter your authenticator app code")
        if user.mfa_secret is None or not verify_mfa_code(decrypt_mfa_secret(user.mfa_secret), body.mfa_code):
            record_login_attempt(db, email, client_ip, success=False)
            raise APIError(401, "INVALID_MFA_CODE", "Incorrect authenticator app code")

    record_login_attempt(db, email, client_ip, success=True)
    user.last_login_at = datetime.now(UTC)
    db.commit()

    # Signing in again ends the session this browser already had.
    previous = resolve_session(db, request.cookies.get(COOKIE_NAME))
    if previous is not None:
        revoke(db, previous)

    # ADR-012: an account with no mfa_secret yet gets a restricted
    # enrollment session, not a full one — it can only reach /mfa/setup and
    # /mfa/enroll (see current_admin_for_enrollment).
    scope = SCOPE_FULL if mfa_enrolled else SCOPE_MFA_ENROLLMENT
    token, session = create_session(db, user.id, scope, request.headers.get("user-agent"))
    set_session_cookie(response, token, session)

    return AdminLoginResponse(
        expires_in=int((session.expires_at - session.created_at).total_seconds()),
        role=cast(Literal["EDITOR", "ADMIN"], user.role),
        mfa_enrollment_required=not mfa_enrolled,
    )


@router.get("/session")
def current_session(admin: AdminPrincipal = Depends(current_admin_for_enrollment)) -> AdminCurrentSessionOut:
    """Who is signed in. The admin app calls this instead of reading a token."""
    return AdminCurrentSessionOut(
        email=admin.email,
        role=cast(Literal["EDITOR", "ADMIN"], admin.role),
        mfa_enrollment_required=admin.session.scope == SCOPE_MFA_ENROLLMENT,
        expires_at=admin.session.expires_at,
        idle_expires_at=idle_expires_at(admin.session),
    )


@router.get("/sessions")
def list_sessions(admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)) -> AdminSessionListOut:
    """This account's live sessions, most recently active first."""
    return AdminSessionListOut(
        items=[
            AdminSessionOut(
                id=row.id,
                created_at=row.created_at,
                last_seen_at=row.last_seen_at,
                expires_at=row.expires_at,
                user_agent=row.user_agent,
                current=row.id == admin.session.id,
            )
            for row in live_sessions_for_user(db, admin.session.user_id)
        ]
    )


@router.post("/logout", status_code=204)
def logout(
    response: Response, admin: AdminPrincipal = Depends(current_admin_for_enrollment), db: Session = Depends(get_db)
) -> None:
    revoke(db, admin.session)
    clear_session_cookie(response)


@router.post("/logout-everywhere", status_code=204)
def logout_everywhere(
    response: Response, admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)
) -> None:
    """Ends every session of this account, this one included."""
    revoke_all_for_user(db, admin.session.user_id)
    clear_session_cookie(response)


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
    response: Response,
    admin: AdminPrincipal = Depends(current_admin_for_enrollment),
    db: Session = Depends(get_db),
) -> MfaStatusResponse:
    if not verify_mfa_code(body.secret, body.code):
        raise APIError(401, "INVALID_MFA_CODE", "Incorrect authenticator app code")
    user = db.get(User, admin.user_id)
    if user is None:
        raise APIError(404, "NOT_FOUND", "Admin user not found")
    if user.mfa_secret is not None:
        # Replacing an enrolled authenticator would let a stolen session take
        # over the account; reset is an operator action, not a self-service one.
        raise APIError(409, "MFA_ALREADY_ENROLLED", "An authenticator is already enrolled")
    user.mfa_secret = encrypt_mfa_secret(body.secret)
    db.commit()
    # An enrollment session never becomes a full one: the editor signs in
    # again with a code, which proves the authenticator works.
    if admin.session.scope == SCOPE_MFA_ENROLLMENT:
        revoke(db, admin.session)
        clear_session_cookie(response)
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
