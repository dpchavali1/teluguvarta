"""T06 acceptance tests: source registry CRUD, the rights gate, and audit
events. Needs real Postgres for the native `source_rights_status` enum and
row-level state, same fixtures as test_admin_auth.py.
"""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from tests.conftest import requires_postgres

pytestmark = requires_postgres

ADMIN_EMAIL = "admin@example.com"
EDITOR_EMAIL = "editor@example.com"
PASSWORD = "correct horse battery staple"


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
    # exercise source admin endpoints, not P0-3/ADR-012's MFA-enrollment gate.
    from app.models import User
    from app.security import create_admin_access_token, hash_password

    user = User(id=uuid.uuid4(), email=email, role=role, password_hash=hash_password(PASSWORD))
    db_session.add(user)
    db_session.commit()

    token, _ = create_admin_access_token(user.id, user.email, role)
    return token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_source_defaults_to_disabled(client, db_session):
    token = _token(client, db_session)

    response = client.post("/v1/admin/sources", json={"name": "Eenadu"}, headers=_auth(token))
    assert response.status_code == 201
    body = response.json()
    assert body["rights_status"] == "DISABLED"
    assert body["active"] is False
    assert body["fail_count"] == 0


def test_cannot_enable_source_without_rights_evidence(client, db_session):
    token = _token(client, db_session)
    source_id = client.post("/v1/admin/sources", json={"name": "Eenadu"}, headers=_auth(token)).json()["id"]

    response = client.patch(
        f"/v1/admin/sources/{source_id}", json={"rights_status": "LINK_ONLY"}, headers=_auth(token)
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "RIGHTS_EVIDENCE_REQUIRED"


def test_enable_source_succeeds_with_full_evidence(client, db_session):
    token = _token(client, db_session)
    source_id = client.post("/v1/admin/sources", json={"name": "Eenadu"}, headers=_auth(token)).json()["id"]

    response = client.patch(
        f"/v1/admin/sources/{source_id}",
        json={
            "rights_status": "LINK_ONLY",
            "rights_evidence_url": "https://eenadu.net/terms",
            "rights_reviewed_at": datetime.now(UTC).isoformat(),
            "reviewer": ADMIN_EMAIL,
        },
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json()["rights_status"] == "LINK_ONLY"


@pytest.mark.parametrize("tier", ["LICENSED_METADATA", "LICENSED_REPURPOSE"])
def test_higher_rights_tiers_rejected_even_with_evidence(client, db_session, tier):
    token = _token(client, db_session)
    source_id = client.post("/v1/admin/sources", json={"name": "Eenadu"}, headers=_auth(token)).json()["id"]

    response = client.patch(
        f"/v1/admin/sources/{source_id}",
        json={
            "rights_status": tier,
            "rights_evidence_url": "https://eenadu.net/terms",
            "rights_reviewed_at": datetime.now(UTC).isoformat(),
            "reviewer": ADMIN_EMAIL,
        },
        headers=_auth(token),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "RIGHTS_TIER_NOT_ENABLED"


def test_editor_cannot_enable_a_source(client, db_session):
    token = _token(client, db_session, role="EDITOR", email=EDITOR_EMAIL)
    source_id = client.post("/v1/admin/sources", json={"name": "Eenadu"}, headers=_auth(token)).json()["id"]

    response = client.patch(
        f"/v1/admin/sources/{source_id}",
        json={
            "rights_status": "LINK_ONLY",
            "rights_evidence_url": "https://eenadu.net/terms",
            "rights_reviewed_at": datetime.now(UTC).isoformat(),
            "reviewer": EDITOR_EMAIL,
        },
        headers=_auth(token),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_editor_can_still_edit_non_rights_fields(client, db_session):
    token = _token(client, db_session, role="EDITOR", email=EDITOR_EMAIL)
    source_id = client.post("/v1/admin/sources", json={"name": "Eenadu"}, headers=_auth(token)).json()["id"]

    response = client.patch(
        f"/v1/admin/sources/{source_id}", json={"refresh_minutes": 30}, headers=_auth(token)
    )
    assert response.status_code == 200
    assert response.json()["refresh_minutes"] == 30


def test_source_mutations_write_audit_events(client, db_session):
    from app.models import AuditEvent

    token = _token(client, db_session)
    source_id = client.post("/v1/admin/sources", json={"name": "Eenadu"}, headers=_auth(token)).json()["id"]
    client.patch(f"/v1/admin/sources/{source_id}", json={"refresh_minutes": 15}, headers=_auth(token))

    events = db_session.scalars(
        select(AuditEvent).where(AuditEvent.entity_id == uuid.UUID(source_id)).order_by(AuditEvent.created_at)
    ).all()
    actions = [e.action for e in events]
    assert actions == ["SOURCE_CREATED", "SOURCE_UPDATED"]
    assert all(e.actor == ADMIN_EMAIL for e in events)


def test_kill_switches_reflect_env(client, db_session, monkeypatch):
    token = _token(client, db_session)
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "true")
    monkeypatch.setenv("AUTO_PUBLISH_CATEGORY_IMMIGRATION", "false")

    response = client.get("/v1/admin/kill-switches", headers=_auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["auto_publish_global"] is True
    assert body["auto_publish_category_immigration"] is False


def test_jobs_endpoint_lists_real_job_health(client, db_session):
    """T08: source health/job visibility must be real once jobs exist, not
    the T04-era stub that always returned []."""
    from app.models import Job

    token = _token(client, db_session)
    db_session.add(Job(type="source_fetch", payload={}, status="FAILED", attempts=5, last_error="boom"))
    db_session.commit()

    response = client.get("/v1/admin/jobs", headers=_auth(token))
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["status"] == "FAILED"
    assert body[0]["attempts"] == 5
    assert body[0]["last_error"] == "boom"


def _enable_body(**overrides):
    body = {
        "name": "Preset Gov Feed",
        "feed_url": "https://example.gov/feed.xml",
        "rights_status": "LINK_ONLY",
        "rights_evidence_url": "https://example.gov/terms",
        "reviewer": ADMIN_EMAIL,
        "active": True,
    }
    body.update(overrides)
    return body


def test_create_and_activate_in_one_call_with_evidence(client, db_session):
    token = _token(client, db_session)

    response = client.post("/v1/admin/sources", json=_enable_body(), headers=_auth(token))
    assert response.status_code == 201
    body = response.json()
    assert body["rights_status"] == "LINK_ONLY"
    assert body["active"] is True
    assert body["reviewer"] == ADMIN_EMAIL
    assert body["rights_reviewed_at"] is not None  # server-stamped


def test_create_and_activate_requires_evidence_url_and_reviewer(client, db_session):
    token = _token(client, db_session)

    for missing in ("rights_evidence_url", "reviewer"):
        response = client.post("/v1/admin/sources", json=_enable_body(**{missing: None}), headers=_auth(token))
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "RIGHTS_EVIDENCE_REQUIRED"


def test_editor_cannot_create_and_activate(client, db_session):
    token = _token(client, db_session, role="EDITOR", email=EDITOR_EMAIL)

    response = client.post("/v1/admin/sources", json=_enable_body(reviewer=EDITOR_EMAIL), headers=_auth(token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_create_rejects_higher_rights_tiers_and_activating_while_disabled(client, db_session):
    token = _token(client, db_session)

    tier = client.post("/v1/admin/sources", json=_enable_body(rights_status="LICENSED_REPURPOSE"), headers=_auth(token))
    assert tier.status_code == 422
    assert tier.json()["error"]["code"] == "RIGHTS_TIER_NOT_ENABLED"

    active_disabled = client.post("/v1/admin/sources", json={"name": "X", "active": True}, headers=_auth(token))
    assert active_disabled.status_code == 422
    assert active_disabled.json()["error"]["code"] == "SOURCE_NOT_ENABLED"


def test_failed_gate_creates_no_source(client, db_session):
    token = _token(client, db_session)
    client.post("/v1/admin/sources", json=_enable_body(name="Ghost", reviewer=None), headers=_auth(token))

    names = [s["name"] for s in client.get("/v1/admin/sources", headers=_auth(token)).json()]
    assert "Ghost" not in names


# ADR-020: description evidence flag.


def _link_only_source(client, token, **rights_evidence):
    source_id = client.post("/v1/admin/sources", json={"name": "State Dept"}, headers=_auth(token)).json()["id"]
    response = client.patch(
        f"/v1/admin/sources/{source_id}",
        json={
            "rights_status": "LINK_ONLY",
            "rights_evidence_url": "https://travel.state.gov/content/travel/en/copyright.html",
            "rights_reviewed_at": datetime.now(UTC).isoformat(),
            "reviewer": ADMIN_EMAIL,
            "rights_evidence": rights_evidence,
        },
        headers=_auth(token),
    )
    assert response.status_code == 200
    return source_id


BASIS = {"public_domain_basis": "U.S. federal government work, 17 U.S.C. §105"}


def test_description_evidence_requires_public_domain_basis(client, db_session):
    token = _token(client, db_session)
    source_id = _link_only_source(client, token)

    response = client.patch(f"/v1/admin/sources/{source_id}", json={"description_evidence": True}, headers=_auth(token))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "DESCRIPTION_EVIDENCE_NOT_ALLOWED"


def test_editor_cannot_turn_on_description_evidence(client, db_session):
    admin_token = _token(client, db_session)
    source_id = _link_only_source(client, admin_token, **BASIS)
    editor_token = _token(client, db_session, role="EDITOR", email=EDITOR_EMAIL)

    response = client.patch(
        f"/v1/admin/sources/{source_id}", json={"description_evidence": True}, headers=_auth(editor_token)
    )
    assert response.status_code == 403


def test_turning_description_evidence_off_clears_stored_text(client, db_session):
    from app.models import Source, SourceItem

    token = _token(client, db_session)
    source_id = _link_only_source(client, token, **BASIS)
    response = client.patch(f"/v1/admin/sources/{source_id}", json={"description_evidence": True}, headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["description_evidence"] is True

    db_session.add(
        SourceItem(source_id=uuid.UUID(source_id), external_id="a", url="https://x.gov/a", title="T", raw_hash="h", description="Advisory text.")
    )
    db_session.commit()

    response = client.patch(f"/v1/admin/sources/{source_id}", json={"rights_status": "DISABLED"}, headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["description_evidence"] is False
    db_session.expire_all()
    assert db_session.get(Source, uuid.UUID(source_id)).description_evidence is False
    assert db_session.scalars(select(SourceItem.description).where(SourceItem.source_id == uuid.UUID(source_id))).all() == [None]


def test_editor_resaving_a_flagged_source_keeps_the_flag(client, db_session):
    admin_token = _token(client, db_session)
    source_id = _link_only_source(client, admin_token, **BASIS)
    client.patch(f"/v1/admin/sources/{source_id}", json={"description_evidence": True}, headers=_auth(admin_token))
    editor_token = _token(client, db_session, role="EDITOR", email=EDITOR_EMAIL)

    response = client.patch(
        f"/v1/admin/sources/{source_id}",
        json={"description_evidence": True, "rights_evidence": BASIS},
        headers=_auth(editor_token),
    )
    assert response.status_code == 200
    assert response.json()["description_evidence"] is True
