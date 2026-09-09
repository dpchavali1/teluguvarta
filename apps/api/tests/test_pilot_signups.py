"""T20 pre-build validation gate: the landing-page signup endpoint (public,
rate-limited, dedupes by email) and its admin read-back."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tests.conftest import requires_postgres

pytestmark = requires_postgres

ADMIN_EMAIL = "admin@example.com"
PASSWORD = "correct horse battery staple"


@pytest.fixture
def client(migrated_database, monkeypatch):
    monkeypatch.setenv("ADMIN_JWT_SECRET", "test-secret")

    from app.db import _engine_for
    from app.main import app
    from app.rate_limit import reset as reset_rate_limits

    _engine_for.cache_clear()
    reset_rate_limits()
    yield TestClient(app)
    reset_rate_limits()
    _engine_for.cache_clear()


@pytest.fixture
def db_session(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _admin_token(client, db_session):
    from app.models import User
    from app.security import hash_password

    user = User(id=uuid.uuid4(), email=ADMIN_EMAIL, role="ADMIN", password_hash=hash_password(PASSWORD))
    db_session.add(user)
    db_session.commit()

    response = client.post("/v1/admin/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_signup_creates_a_pilot_signup(client):
    response = client.post(
        "/v1/pilot-signups",
        json={"email": "Pilot.User@Example.com", "segment": "professional", "example_feed": "professional"},
    )
    assert response.status_code == 201
    body = response.json()
    assert "id" in body and "created_at" in body


def test_signup_rejects_invalid_email(client):
    response = client.post("/v1/pilot-signups", json={"email": "not-an-email"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_EMAIL"


def test_signup_is_idempotent_by_email_and_normalizes_case(client, db_session):
    from app.models import PilotSignup

    first = client.post(
        "/v1/pilot-signups", json={"email": "Repeat@Example.com", "segment": "professional", "example_feed": "professional"}
    )
    assert first.status_code == 201

    second = client.post(
        "/v1/pilot-signups",
        json={"email": "repeat@example.com", "segment": "international_student", "example_feed": "international_student"},
    )
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]

    rows = db_session.query(PilotSignup).all()
    assert len(rows) == 1
    assert rows[0].email == "repeat@example.com"
    assert rows[0].segment == "international_student"


def test_signup_is_rate_limited(client):
    for i in range(5):
        response = client.post("/v1/pilot-signups", json={"email": f"user{i}@example.com"})
        assert response.status_code == 201
    limited = client.post("/v1/pilot-signups", json={"email": "user6@example.com"})
    assert limited.status_code == 429


def test_admin_can_list_pilot_signups(client, db_session):
    token = _admin_token(client, db_session)
    client.post("/v1/pilot-signups", json={"email": "listed@example.com", "segment": "family_parent"})

    response = client.get("/v1/admin/pilot-signups", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["email"] == "listed@example.com"
    assert body["items"][0]["segment"] == "family_parent"


def test_admin_pilot_signups_requires_auth(client):
    response = client.get("/v1/admin/pilot-signups")
    assert response.status_code == 401
