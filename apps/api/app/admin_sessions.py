"""Server-side admin sessions behind an HttpOnly cookie (ADR-028 option A).

The browser holds a random id in `tte_admin` (HttpOnly, Secure, SameSite=Strict,
host-only on the API, Path=/v1/admin), so script on the admin origin can't read
it. The row stores the id's SHA-256. A session ends at whichever comes first: 30
minutes without a request, 12 hours after login, logout, or sign-out-everywhere.

CSRF: SameSite=Strict keeps the cookie off cross-site requests, and every
state-changing admin request must also carry `X-TTE-Admin: 1`, which a
cross-site form can't send and a cross-origin script can't send without
passing the API's CORS allowlist.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Request, Response
from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.errors import APIError
from app.models import AdminSession

COOKIE_NAME = "tte_admin"
COOKIE_PATH = "/v1/admin"
CSRF_HEADER = "X-TTE-Admin"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

SCOPE_FULL = "full"
SCOPE_MFA_ENROLLMENT = "mfa_enrollment"

IDLE_TIMEOUT = timedelta(minutes=int(os.environ.get("ADMIN_SESSION_IDLE_MINUTES", "30")))
ABSOLUTE_TIMEOUT = timedelta(hours=int(os.environ.get("ADMIN_SESSION_MAX_HOURS", "12")))
# ADR-012: enough to scan a QR code and enter one code, not a standing credential.
ENROLLMENT_TIMEOUT = timedelta(minutes=5)
# last_seen_at is written at most this often, not on every request.
TOUCH_INTERVAL = timedelta(seconds=60)
# Ended sessions are kept this long for the session list, then deleted by `cleanup`.
RETENTION = timedelta(days=30)
PURGE_BATCH = 1_000
USER_AGENT_MAX = 300


def cookie_secure() -> bool:
    """Off only for plain-http local development (`ADMIN_COOKIE_SECURE=false`)."""
    return os.environ.get("ADMIN_COOKIE_SECURE", "true").strip().lower() != "false"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def require_csrf_header(request: Request) -> None:
    if request.method not in SAFE_METHODS and request.headers.get(CSRF_HEADER) != "1":
        raise APIError(403, "CSRF_HEADER_REQUIRED", f"State-changing admin requests must send {CSRF_HEADER}: 1")


def create_session(
    db: Session, user_id: uuid.UUID, scope: str, user_agent: str | None, now: datetime | None = None
) -> tuple[str, AdminSession]:
    now = now or datetime.now(UTC)
    token = secrets.token_urlsafe(32)
    lifetime = ENROLLMENT_TIMEOUT if scope == SCOPE_MFA_ENROLLMENT else ABSOLUTE_TIMEOUT
    session = AdminSession(
        id=uuid.uuid4(),
        token_hash=hash_token(token),
        user_id=user_id,
        scope=scope,
        user_agent=(user_agent or "")[:USER_AGENT_MAX] or None,
        created_at=now,
        last_seen_at=now,
        expires_at=now + lifetime,
    )
    db.add(session)
    db.commit()
    return token, session


def idle_expires_at(session: AdminSession) -> datetime:
    return min(session.expires_at, session.last_seen_at + IDLE_TIMEOUT)


def is_live(session: AdminSession, now: datetime) -> bool:
    return session.revoked_at is None and now < idle_expires_at(session)


def resolve_session(db: Session, token: str | None, now: datetime | None = None) -> AdminSession | None:
    """The live session for a cookie value, with its activity time refreshed."""
    if not token:
        return None
    now = now or datetime.now(UTC)
    session = db.scalar(select(AdminSession).where(AdminSession.token_hash == hash_token(token)))
    if session is None or not is_live(session, now):
        return None
    if now - session.last_seen_at >= TOUCH_INTERVAL:
        session.last_seen_at = now
        db.commit()
    return session


def revoke(db: Session, session: AdminSession, now: datetime | None = None) -> None:
    if session.revoked_at is None:
        session.revoked_at = now or datetime.now(UTC)
        db.commit()


def revoke_all_for_user(db: Session, user_id: uuid.UUID, now: datetime | None = None) -> int:
    result = db.execute(
        update(AdminSession)
        .where(AdminSession.user_id == user_id, AdminSession.revoked_at.is_(None))
        .values(revoked_at=now or datetime.now(UTC))
    )
    db.commit()
    return result.rowcount or 0


def live_sessions_for_user(db: Session, user_id: uuid.UUID, now: datetime | None = None) -> list[AdminSession]:
    now = now or datetime.now(UTC)
    rows = db.scalars(
        select(AdminSession)
        .where(AdminSession.user_id == user_id, AdminSession.revoked_at.is_(None), AdminSession.expires_at > now)
        .order_by(AdminSession.last_seen_at.desc())
    ).all()
    return [row for row in rows if is_live(row, now)]


def purge_ended_sessions(db: Session, now: datetime) -> int:
    """Deletes sessions that ended (revoked or expired) more than RETENTION ago."""
    cutoff = now - RETENTION
    ids = db.scalars(
        select(AdminSession.id)
        .where(or_(AdminSession.revoked_at < cutoff, AdminSession.expires_at < cutoff))
        .limit(PURGE_BATCH)
    ).all()
    if not ids:
        return 0
    db.execute(delete(AdminSession).where(AdminSession.id.in_(ids)))
    db.commit()
    return len(ids)


def set_session_cookie(response: Response, token: str, session: AdminSession) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int((session.expires_at - session.created_at).total_seconds()),
        path=COOKIE_PATH,
        secure=cookie_secure(),
        httponly=True,
        samesite="strict",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH, secure=cookie_secure(), httponly=True, samesite="strict")
