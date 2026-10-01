"""Auth dependencies.

`current_user` (end-user auth) implements ADR-006's device-scoped anonymous
identity as of T17: the client mints its own opaque, unguessable token (a
UUID generated on first launch, per the mobile/web onboarding flow) and
sends it as `Authorization: Bearer <token>` on every request. There is no
separate "issue me a token" round trip — the first request bearing a given
token get-or-creates the `users` row for it. ADR-006 explicitly left this
resolution to "a later ticket"; T17 is that ticket, since push tokens and
notification preferences are the first state that must be looked up outside
a request (by the `notification_dispatch` job), so it can no longer be
request-scoped like T16's query-param preferences.

Review #15: the token must look like one a client mints (16–128 URL-safe
characters: a UUID, or the older mobile fallback), and creating a user for a
new token is rate-limited per client address.

`current_admin` checks the server-side session named by the `tte_admin`
HttpOnly cookie that `POST /v1/admin/auth/login` sets (ADR-028; it replaced
a bearer JWT kept in localStorage). Every request re-reads the account (review
#15): a deleted or demoted account loses access at once, and the first such
request also revokes all of its sessions. State-changing requests must send
`X-TTE-Admin: 1` (CSRF; see app/admin_sessions.py).

Per ADR-012, a login for an account with no `mfa_secret` yet gets a
`mfa_enrollment` session instead of a full one. `current_admin` rejects the
enrollment scope outright; `current_admin_for_enrollment` (used only by
`/mfa/setup`, `/mfa/enroll`, `/session` and `/logout`) accepts either.
"""

import re
import uuid

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.admin_sessions import (
    COOKIE_NAME,
    SCOPE_MFA_ENROLLMENT,
    require_csrf_header,
    resolve_session,
    revoke_all_for_user,
)
from app.db import get_db
from app.errors import APIError
from app.models import AdminSession, User
from app.observability.logging import set_actor
from app.rate_limit import rate_limit_new_user

ADMIN_ROLES = {"EDITOR", "ADMIN"}
CLIENT_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,128}")


class Principal:
    def __init__(self, user_id: uuid.UUID, token: str) -> None:
        self.user_id = user_id
        self.token = token


class AdminPrincipal:
    def __init__(self, user_id: str, email: str, role: str, session: AdminSession) -> None:
        self.user_id = user_id
        self.email = email
        self.role = role
        self.session = session


def current_user(
    request: Request, authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise APIError(401, "UNAUTHENTICATED", "Missing or invalid bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not CLIENT_TOKEN_PATTERN.fullmatch(token):
        raise APIError(401, "UNAUTHENTICATED", "Missing or invalid bearer token")

    user = db.scalars(select(User).where(User.client_token == token)).first()
    if user is None:
        rate_limit_new_user(request)
        # on_conflict_do_nothing + reselect (same pattern as
        # app/jobs/queue.py::enqueue_job) so two concurrent first-requests
        # for the same brand-new token can't race on the unique constraint.
        insert_stmt = pg_insert(User).values(id=uuid.uuid4(), client_token=token)
        insert_stmt = insert_stmt.on_conflict_do_nothing(index_elements=[User.client_token])
        db.execute(insert_stmt)
        db.commit()
        user = db.scalars(select(User).where(User.client_token == token)).first()
    actor = str(user.id)
    request.state.actor = actor
    set_actor(actor)
    return Principal(user_id=user.id, token=token)


def _admin_principal(request: Request, db: Session, *, allow_enrollment: bool) -> AdminPrincipal:
    session = resolve_session(db, request.cookies.get(COOKIE_NAME))
    if session is None:
        raise APIError(401, "UNAUTHENTICATED", "Not signed in, or the session has expired")
    require_csrf_header(request)
    user = db.get(User, session.user_id)
    if user is None or user.deleted_at is not None or user.role not in ADMIN_ROLES:
        # ADR-028: deleting or demoting an account revokes its sessions. No
        # API path does either, so the first request after it happens does.
        revoke_all_for_user(db, session.user_id)
        if user is not None and user.deleted_at is None:
            raise APIError(403, "FORBIDDEN", "This account does not have admin access")
        raise APIError(401, "UNAUTHENTICATED", "Not signed in, or the session has expired")
    if session.scope == SCOPE_MFA_ENROLLMENT and not allow_enrollment:
        raise APIError(403, "MFA_ENROLLMENT_REQUIRED", "Complete MFA enrollment before using this endpoint")
    request.state.actor = user.email
    set_actor(user.email)
    return AdminPrincipal(user_id=str(user.id), email=user.email, role=user.role, session=session)


def current_admin(request: Request, db: Session = Depends(get_db)) -> AdminPrincipal:
    return _admin_principal(request, db, allow_enrollment=False)


def current_admin_for_enrollment(request: Request, db: Session = Depends(get_db)) -> AdminPrincipal:
    """ADR-012: accepts a full session or a restricted `mfa_enrollment` one, so
    a privileged user with no `mfa_secret` can reach the endpoints that let
    them set one up (and can see and end that session)."""
    return _admin_principal(request, db, allow_enrollment=True)
