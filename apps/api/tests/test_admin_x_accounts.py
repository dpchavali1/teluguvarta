"""X1 acceptance tests: X account registry fields, linked to a Source, reuse
the same rights gate as any other source (ADR-002) — no parallel approval
flow. Needs real Postgres, same fixtures as test_admin_sources.py.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from tests.conftest import requires_postgres

pytestmark = requires_postgres

ADMIN_EMAIL = "admin@example.com"


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


def _token(client, db_session, *, role="ADMIN", email=ADMIN_EMAIL):
    from app.models import User
    from app.security import hash_password

    user = User(id=uuid.uuid4(), email=email, role=role, password_hash=hash_password("correct horse battery staple"))
    db_session.add(user)
    db_session.commit()

    response = client.post("/v1/admin/auth/login", json={"email": email, "password": "correct horse battery staple"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_source(client, token, name="Official X account"):
    response = client.post("/v1/admin/sources", json={"name": name, "source_type": "X_ACCOUNT"}, headers=_auth(token))
    assert response.status_code == 201
    return response.json()["id"]


def test_create_x_account_links_to_source(client, db_session):
    token = _token(client, db_session)
    source_id = _make_source(client, token)

    response = client.post(
        f"/v1/admin/sources/{source_id}/x-account",
        json={"x_user_id": "123456789", "handle": "@example", "priority": 1},
        headers=_auth(token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["source_id"] == source_id
    assert body["x_user_id"] == "123456789"
    # Reused from the linked Source, not a parallel field.
    assert body["rights_status"] == "DISABLED"
    assert body["active"] is False


def test_x_account_cannot_be_active_without_source_rights_evidence(client, db_session):
    """Enabling the X account goes through T06's existing rights gate on the
    linked Source — there is no separate X-account approval endpoint."""
    token = _token(client, db_session)
    source_id = _make_source(client, token)
    client.post(
        f"/v1/admin/sources/{source_id}/x-account",
        json={"x_user_id": "123456789", "handle": "@example"},
        headers=_auth(token),
    )

    response = client.patch(
        f"/v1/admin/sources/{source_id}", json={"rights_status": "LINK_ONLY"}, headers=_auth(token)
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "RIGHTS_EVIDENCE_REQUIRED"

    listed = client.get("/v1/admin/x-accounts", headers=_auth(token)).json()
    assert listed[0]["rights_status"] == "DISABLED"


def test_cannot_link_two_x_accounts_to_one_source(client, db_session):
    token = _token(client, db_session)
    source_id = _make_source(client, token)
    client.post(
        f"/v1/admin/sources/{source_id}/x-account",
        json={"x_user_id": "111", "handle": "@one"},
        headers=_auth(token),
    )

    response = client.post(
        f"/v1/admin/sources/{source_id}/x-account",
        json={"x_user_id": "222", "handle": "@two"},
        headers=_auth(token),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "X_ACCOUNT_ALREADY_LINKED"


def test_cannot_reuse_x_user_id_across_sources(client, db_session):
    token = _token(client, db_session)
    source_a = _make_source(client, token, "Account A")
    source_b = _make_source(client, token, "Account B")
    client.post(
        f"/v1/admin/sources/{source_a}/x-account",
        json={"x_user_id": "999", "handle": "@a"},
        headers=_auth(token),
    )

    response = client.post(
        f"/v1/admin/sources/{source_b}/x-account",
        json={"x_user_id": "999", "handle": "@b"},
        headers=_auth(token),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "X_USER_ID_ALREADY_LINKED"


def test_update_x_account_since_id_and_health_fields_queryable(client, db_session):
    token = _token(client, db_session)
    source_id = _make_source(client, token)
    client.post(
        f"/v1/admin/sources/{source_id}/x-account",
        json={"x_user_id": "123456789", "handle": "@example"},
        headers=_auth(token),
    )

    response = client.patch(
        f"/v1/admin/sources/{source_id}/x-account", json={"since_id": "1700000000000000000"}, headers=_auth(token)
    )
    assert response.status_code == 200
    assert response.json()["since_id"] == "1700000000000000000"

    listed = client.get("/v1/admin/x-accounts", headers=_auth(token)).json()
    assert listed[0]["since_id"] == "1700000000000000000"
    assert "last_success_at" in listed[0]
    assert "last_error_at" in listed[0]


def test_x_account_mutations_write_audit_events(client, db_session):
    from app.models import AuditEvent

    token = _token(client, db_session)
    source_id = _make_source(client, token)
    account_id = client.post(
        f"/v1/admin/sources/{source_id}/x-account",
        json={"x_user_id": "123456789", "handle": "@example"},
        headers=_auth(token),
    ).json()["id"]
    client.patch(f"/v1/admin/sources/{source_id}/x-account", json={"priority": 2}, headers=_auth(token))

    events = db_session.scalars(
        select(AuditEvent).where(AuditEvent.entity_id == uuid.UUID(account_id)).order_by(AuditEvent.created_at)
    ).all()
    assert [e.action for e in events] == ["X_ACCOUNT_CREATED", "X_ACCOUNT_UPDATED"]
