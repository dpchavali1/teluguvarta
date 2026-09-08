"""T05 acceptance tests: admin login, RBAC on /v1/admin/*, and rate limiting.

Needs real Postgres (a seeded user, real login attempts) so these use the
same `migrated_database` fixture as the T03 schema tests, and skip the same
way when no Postgres is reachable.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tests.conftest import requires_postgres

pytestmark = requires_postgres

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "correct horse battery staple"


@pytest.fixture
def client(migrated_database, monkeypatch):
    monkeypatch.setenv("ADMIN_JWT_SECRET", "test-secret")

    from app.db import _engine_for
    from app.main import app

    _engine_for.cache_clear()
    yield TestClient(app)
    _engine_for.cache_clear()


@pytest.fixture
def db_session(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _seed_admin(db_session, *, email=ADMIN_EMAIL, password=ADMIN_PASSWORD, role="ADMIN"):
    from app.models import User
    from app.security import hash_password

    user = User(id=uuid.uuid4(), email=email, role=role, password_hash=hash_password(password))
    db_session.add(user)
    db_session.commit()
    return user


def test_login_succeeds_and_token_grants_admin_access(client, db_session):
    _seed_admin(db_session)

    response = client.post("/v1/admin/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "ADMIN"
    token = body["access_token"]

    admin_response = client.get("/v1/admin/sources", headers={"Authorization": f"Bearer {token}"})
    assert admin_response.status_code == 200


def test_login_rejects_wrong_password(client, db_session):
    _seed_admin(db_session)

    response = client.post("/v1/admin/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_rejects_unknown_email(client, db_session):
    response = client.post(
        "/v1/admin/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_non_staff_user_cannot_get_admin_token(client, db_session):
    # A user with no role at all (an ordinary end user) has no password to
    # log in with, but this also guards against ever minting an admin token
    # for a role outside {EDITOR, ADMIN}.
    from app.security import create_admin_access_token

    user = _seed_admin(db_session, role="ADMIN")
    token, _ = create_admin_access_token(user.id, user.email, "SOMETHING_ELSE")

    response = client.get("/v1/admin/sources", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_admin_route_rejects_expired_token(client, db_session, monkeypatch):
    import jwt

    from app.security import ADMIN_JWT_ALGORITHM

    user = _seed_admin(db_session)
    expired_payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": "ADMIN",
        "iat": datetime.now(UTC) - timedelta(hours=1),
        "exp": datetime.now(UTC) - timedelta(minutes=1),
    }
    expired_token = jwt.encode(expired_payload, "test-secret", algorithm=ADMIN_JWT_ALGORITHM)

    response = client.get("/v1/admin/sources", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401


def test_login_is_rate_limited_after_n_attempts(client, db_session):
    from app.models import AdminLoginAttempt

    _seed_admin(db_session)

    # Fast-forward past the attempt count without waiting on real wall-clock
    # time or firing five real HTTP requests: insert the attempt history the
    # rate limiter reads directly.
    now = datetime.now(UTC)
    for _ in range(5):
        db_session.add(AdminLoginAttempt(email=ADMIN_EMAIL, ip="127.0.0.1", success=False, created_at=now))
    db_session.commit()

    response = client.post("/v1/admin/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"


def test_login_rate_limit_does_not_affect_other_emails(client, db_session):
    from app.models import AdminLoginAttempt

    _seed_admin(db_session)
    _seed_admin(db_session, email="other-admin@example.com")

    now = datetime.now(UTC)
    for _ in range(5):
        db_session.add(AdminLoginAttempt(email=ADMIN_EMAIL, ip="127.0.0.1", success=False, created_at=now))
    db_session.commit()

    response = client.post(
        "/v1/admin/auth/login",
        json={"email": "other-admin@example.com", "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
