"""T19 hardening acceptance tests: cross-system account deletion (§16/§5.5)
and request-volume rate limiting on search/admin (§16 baseline). MFA and the
budget-breach auto-publish gate have their own tests in test_admin_auth.py
and test_editorial_workflow.py respectively — this file covers the two
pieces that didn't already have an obvious home.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import rate_limit
from app.models import Notification, Profile, PushToken, Story, User, UserTopic
from tests.conftest import requires_postgres

pytestmark = requires_postgres


@pytest.fixture
def client(migrated_database):
    from app.db import _engine_for
    from app.main import app

    _engine_for.cache_clear()
    rate_limit.reset()
    yield TestClient(app)
    rate_limit.reset()
    _engine_for.cache_clear()


@pytest.fixture
def db_session(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_account_deletion_cascades_across_every_table(client, db_session):
    token = str(uuid.uuid4())

    # Create the user and attach state to every table T17 added for it.
    me = client.get("/v1/me", headers=_auth(token))
    assert me.status_code == 200
    user_id = me.json()["id"]

    client.patch(
        "/v1/me/preferences",
        json={"residence_country": "US", "topic_slugs": []},
        headers=_auth(token),
    )
    client.post("/v1/me/push-tokens", json={"platform": "ios", "token": "expo-token-1"}, headers=_auth(token))

    story = Story(canonical_slug=f"story-{uuid.uuid4()}", status="PUBLISHED")
    db_session.add(story)
    db_session.commit()
    db_session.add(Notification(user_id=user_id, story_id=story.id, type="DAILY_BRIEFING", notification_key="k1"))
    db_session.commit()

    assert db_session.get(Profile, uuid.UUID(user_id)) is not None
    assert db_session.scalars(select(PushToken).where(PushToken.user_id == user_id)).first() is not None
    assert db_session.scalars(select(Notification).where(Notification.user_id == user_id)).first() is not None

    response = client.request("DELETE", "/v1/me/account", headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["deleted"] is True

    assert db_session.get(User, uuid.UUID(user_id)) is None
    assert db_session.get(Profile, uuid.UUID(user_id)) is None
    assert db_session.scalars(select(PushToken).where(PushToken.user_id == user_id)).first() is None
    assert db_session.scalars(select(Notification).where(Notification.user_id == user_id)).first() is None
    assert db_session.scalars(select(UserTopic).where(UserTopic.user_id == user_id)).first() is None

    # The old token is fully forgotten — reusing it just mints a brand-new,
    # empty identity rather than resurrecting any deleted state.
    me_again = client.get("/v1/me", headers=_auth(token))
    assert me_again.status_code == 200
    assert me_again.json()["id"] != user_id
    assert me_again.json()["profile"]["residence_country"] is None


def test_account_deletion_is_idempotent(client):
    token = str(uuid.uuid4())
    client.get("/v1/me", headers=_auth(token))

    first = client.request("DELETE", "/v1/me/account", headers=_auth(token))
    assert first.status_code == 200

    # A second delete with the same (now-forgotten) token just re-creates
    # and immediately deletes a fresh empty user — never an error.
    second = client.request("DELETE", "/v1/me/account", headers=_auth(token))
    assert second.status_code == 200


def test_search_is_rate_limited_per_client(client, monkeypatch):
    monkeypatch.setattr(rate_limit, "SEARCH_MAX_REQUESTS", 3)

    for _ in range(3):
        response = client.get("/v1/search", params={"q": "test"})
        assert response.status_code == 200

    limited = client.get("/v1/search", params={"q": "test"})
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"


def test_admin_surface_is_rate_limited_per_client(client, db_session, monkeypatch):
    from tests.admin_session_helpers import admin_auth, admin_session_token

    monkeypatch.setattr(rate_limit, "ADMIN_MAX_REQUESTS", 2)

    user = User(id=uuid.uuid4(), email="admin@example.com", role="ADMIN")
    db_session.add(user)
    db_session.commit()
    headers = admin_auth(admin_session_token(db_session, user.id))

    for _ in range(2):
        assert client.get("/v1/admin/sources", headers=headers).status_code == 200

    limited = client.get("/v1/admin/sources", headers=headers)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
