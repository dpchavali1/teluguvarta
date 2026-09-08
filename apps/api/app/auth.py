"""Auth dependencies — STUBBED pending T05 (admin authentication).

These only check that a bearer token is present so the endpoint contracts
(status codes, response shapes) are final now, per T04's scope. Neither
verifies the token, resolves a real user, nor checks a role/permission.
T05 must replace the body of both functions with real verification before
any of this ships.
"""

from fastapi import Header

from app.errors import APIError


class Principal:
    def __init__(self, token: str) -> None:
        self.token = token


def current_user(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise APIError(401, "UNAUTHENTICATED", "Missing or invalid bearer token")
    return Principal(token=authorization.removeprefix("Bearer "))


def current_admin(authorization: str | None = Header(default=None)) -> Principal:
    # T05 will add real role/permission checks. This is intentionally the
    # same check as current_user — it exists as a separate dependency so
    # admin routes already declare the right shape of guard.
    if not authorization or not authorization.startswith("Bearer "):
        raise APIError(401, "UNAUTHENTICATED", "Missing or invalid bearer token")
    return Principal(token=authorization.removeprefix("Bearer "))
