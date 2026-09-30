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

`current_admin` does real verification as of T05: a signed, short-lived JWT
(see app/security.py) issued by `POST /v1/admin/auth/login`, carrying a
`role` claim. Since review #15 the claim alone isn't trusted: every request
re-reads the account, so a deleted or demoted account loses access at once
instead of when its token expires, and the stored role is what's enforced.

Per ADR-012, a login for an account with no `mfa_secret` yet gets a
`scope: mfa_enrollment` token instead of `scope: full`. `current_admin`
rejects the enrollment scope outright; `current_admin_for_enrollment`
(used only by `/mfa/setup` and `/mfa/enroll`) accepts either.
"""

import re
import uuid

from fastapi import Depends, Header, Request
from jwt import PyJWTError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import APIError
from app.models import User
from app.observability.logging import set_actor
from app.rate_limit import rate_limit_new_user
from app.security import decode_admin_access_token

ADMIN_ROLES = {"EDITOR", "ADMIN"}
CLIENT_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,128}")


class Principal:
    def __init__(self, user_id: uuid.UUID, token: str) -> None:
        self.user_id = user_id
        self.token = token


class AdminPrincipal:
    def __init__(self, user_id: str, email: str, role: str) -> None:
        self.user_id = user_id
        self.email = email
        self.role = role


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


def _decode_bearer_admin_token(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise APIError(401, "UNAUTHENTICATED", "Missing or invalid bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        return decode_admin_access_token(token)
    except PyJWTError:
        raise APIError(401, "UNAUTHENTICATED", "Invalid or expired token")


def _admin_principal_from_claims(request: Request, claims: dict, db: Session) -> AdminPrincipal:
    if claims.get("role") not in ADMIN_ROLES:
        raise APIError(403, "FORBIDDEN", "This account does not have admin access")
    try:
        user_id = uuid.UUID(str(claims.get("sub")))
    except ValueError:
        raise APIError(401, "UNAUTHENTICATED", "Invalid or expired token")
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise APIError(401, "UNAUTHENTICATED", "Invalid or expired token")
    if user.role not in ADMIN_ROLES:
        raise APIError(403, "FORBIDDEN", "This account does not have admin access")
    request.state.actor = user.email
    set_actor(user.email)
    return AdminPrincipal(user_id=str(user.id), email=user.email, role=user.role)


def current_admin(
    request: Request, authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> AdminPrincipal:
    claims = _decode_bearer_admin_token(authorization)
    if claims.get("scope") == "mfa_enrollment":
        raise APIError(403, "MFA_ENROLLMENT_REQUIRED", "Complete MFA enrollment before using this endpoint")
    return _admin_principal_from_claims(request, claims, db)


def current_admin_for_enrollment(
    request: Request, authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> AdminPrincipal:
    """ADR-012: accepts a full session token or a restricted `mfa_enrollment`
    token — used only by `/mfa/setup` and `/mfa/enroll` so a privileged user
    with no `mfa_secret` can reach the endpoints that let them set one up."""
    claims = _decode_bearer_admin_token(authorization)
    return _admin_principal_from_claims(request, claims, db)
