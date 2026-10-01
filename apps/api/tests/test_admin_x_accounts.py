"""X1 acceptance tests: X account registry fields, linked to a Source, reuse
the same rights gate as any other source (ADR-002) — no parallel approval
flow. Needs real Postgres, same fixtures as test_admin_sources.py.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from tests.admin_session_helpers import admin_auth
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
    # Mints a full-session token directly rather than via /login: these tests
    # exercise X-account admin endpoints, not P0-3/ADR-012's MFA-enrollment gate.
    from app.models import User
    from app.security import hash_password
    from tests.admin_session_helpers import admin_session_token

    user = User(id=uuid.uuid4(), email=email, role=role, password_hash=hash_password("correct horse battery staple"))
    db_session.add(user)
    db_session.commit()

    token = admin_session_token(db_session, user.id)
    return token


def _auth(token):
    return admin_auth(token)


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


def test_x_account_list_surfaces_health_and_cost_fields(client, db_session):
    """X4 acceptance: admin can see health/poll-state/errors/cost/active
    state per X account without reading logs directly."""
    token = _token(client, db_session)
    source_id = _make_source(client, token)
    client.post(
        f"/v1/admin/sources/{source_id}/x-account",
        json={"x_user_id": "123456789", "handle": "@example"},
        headers=_auth(token),
    )

    listed = client.get("/v1/admin/x-accounts", headers=_auth(token)).json()
    account = listed[0]
    assert account["fail_count"] == 0
    assert account["circuit_breaker_tripped"] is False
    assert account["recent_error_count_24h"] == 0
    assert account["month_to_date_cost_usd"] == 0
    assert account["budget_paused"] is False


def test_budget_guard_pauses_only_low_priority_x_accounts(client, db_session, monkeypatch):
    """X4 acceptance: a simulated budget breach flags `budget_class="LOW"`
    accounts as paused and leaves a higher-priority account untouched."""
    from app.x.budget import record_call

    monkeypatch.setenv("MONTHLY_X_API_BUDGET_USD", "1")
    token = _token(client, db_session)

    low_source_id = _make_source(client, token, "Low priority account")
    high_source_id = _make_source(client, token, "High priority account")
    low_account = client.post(
        f"/v1/admin/sources/{low_source_id}/x-account",
        json={"x_user_id": "111", "handle": "@low", "budget_class": "LOW"},
        headers=_auth(token),
    ).json()
    high_account = client.post(
        f"/v1/admin/sources/{high_source_id}/x-account",
        json={"x_user_id": "222", "handle": "@high", "budget_class": "STANDARD"},
        headers=_auth(token),
    ).json()

    record_call(db_session, x_account_id=uuid.UUID(high_account["id"]), posts_read=0, cost_usd=5.0, status="OK")
    db_session.commit()

    listed = {row["id"]: row for row in client.get("/v1/admin/x-accounts", headers=_auth(token)).json()}
    assert listed[low_account["id"]]["budget_paused"] is True
    assert listed[high_account["id"]]["budget_paused"] is False


def test_manual_pause_of_one_x_account_does_not_affect_another(client, db_session):
    """X4 acceptance: manual pause reuses T06's per-source `active` kill
    switch, which is already scoped one-to-one to an X account — pausing
    one source must not touch any other account's `active` state."""
    token = _token(client, db_session)
    source_a = _make_source(client, token, "Account A")
    source_b = _make_source(client, token, "Account B")
    client.post(
        f"/v1/admin/sources/{source_a}/x-account",
        json={"x_user_id": "333", "handle": "@a", "budget_class": "STANDARD"},
        headers=_auth(token),
    )
    client.post(
        f"/v1/admin/sources/{source_b}/x-account",
        json={"x_user_id": "444", "handle": "@b", "budget_class": "STANDARD"},
        headers=_auth(token),
    )
    # Give both sources rights evidence so `active` can be toggled true.
    for source_id in (source_a, source_b):
        client.patch(
            f"/v1/admin/sources/{source_id}",
            json={
                "rights_status": "LINK_ONLY",
                "rights_evidence_url": "https://example.com/evidence",
                "rights_reviewed_at": "2026-01-01T00:00:00Z",
                "reviewer": "reviewer@example.com",
            },
            headers=_auth(token),
        )

    client.patch(f"/v1/admin/sources/{source_a}", json={"active": True}, headers=_auth(token))
    client.patch(f"/v1/admin/sources/{source_b}", json={"active": True}, headers=_auth(token))
    client.patch(f"/v1/admin/sources/{source_a}", json={"active": False}, headers=_auth(token))

    listed = {row["source_id"]: row for row in client.get("/v1/admin/x-accounts", headers=_auth(token)).json()}
    assert listed[source_a]["active"] is False
    assert listed[source_b]["active"] is True


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
