"""Auth dependencies.

`current_user` (end-user auth) is still STUBBED — it only checks that a
bearer token is present. End-user auth is out of scope for T05 (admin-only,
see docs/tickets/T05.md); its real design is ADR-006, not yet implemented.

`current_admin` does real verification as of T05: a signed, short-lived JWT
(see app/security.py) issued by `POST /v1/admin/auth/login`, carrying a
`role` claim that must be `EDITOR` or `ADMIN`.
"""

from fastapi import Header
from jwt import PyJWTError

from app.errors import APIError
from app.security import decode_admin_access_token

ADMIN_ROLES = {"EDITOR", "ADMIN"}


class Principal:
    def __init__(self, token: str) -> None:
        self.token = token


class AdminPrincipal:
    def __init__(self, user_id: str, email: str, role: str) -> None:
        self.user_id = user_id
        self.email = email
        self.role = role


def current_user(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise APIError(401, "UNAUTHENTICATED", "Missing or invalid bearer token")
    return Principal(token=authorization.removeprefix("Bearer "))


def current_admin(authorization: str | None = Header(default=None)) -> AdminPrincipal:
    if not authorization or not authorization.startswith("Bearer "):
        raise APIError(401, "UNAUTHENTICATED", "Missing or invalid bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        claims = decode_admin_access_token(token)
    except PyJWTError:
        raise APIError(401, "UNAUTHENTICATED", "Invalid or expired token")
    role = claims.get("role")
    if role not in ADMIN_ROLES:
        raise APIError(403, "FORBIDDEN", "This account does not have admin access")
    return AdminPrincipal(user_id=claims["sub"], email=claims["email"], role=role)
