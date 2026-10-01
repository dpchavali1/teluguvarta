"""Test helpers for ADR-028 admin sessions: a session row plus the request
headers a browser would send (the cookie and the CSRF header)."""

import uuid

from sqlalchemy.orm import Session

from app.admin_sessions import COOKIE_NAME, CSRF_HEADER, SCOPE_FULL, create_session


def admin_session_token(db: Session, user_id: uuid.UUID, scope: str = SCOPE_FULL) -> str:
    token, _ = create_session(db, user_id, scope, "pytest")
    return token


def admin_auth(token: str) -> dict:
    return {"Cookie": f"{COOKIE_NAME}={token}", CSRF_HEADER: "1"}
