"""Review #15 hardening: the scheduled feed fetch gets the probe's SSRF/size
policy, admin tokens are re-checked against the account, and anonymous
tokens are bounded with a per-client limit on creating users."""

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import rate_limit
from app.adapters import safe_fetch
from app.adapters.openfema import OpenFemaAdapter
from app.adapters.rss import RssFeedAdapter
from app.adapters.safe_fetch import FeedFetchError
from app.models import Source, User
from tests.conftest import requires_postgres

RSS = b'<?xml version="1.0"?><rss version="2.0"><channel><item><title>One</title><link>https://ex.com/1</link></item></channel></rss>'


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_source_fetch_refuses_private_host_before_connecting(monkeypatch):
    monkeypatch.setattr(safe_fetch, "_resolve", lambda host: ["169.254.169.254"])
    calls = []
    adapter = RssFeedAdapter(Source(name="s", feed_url="http://metadata/feed"))
    with pytest.raises(FeedFetchError, match="public"):
        adapter.fetch(_client(lambda r: calls.append(r) or httpx.Response(200, content=RSS)))
    assert not calls


def test_source_fetch_refuses_redirects_and_oversize_bodies(monkeypatch):
    adapter = RssFeedAdapter(Source(name="s", feed_url="https://ex.com/feed"))
    with pytest.raises(FeedFetchError, match="redirects"):
        adapter.fetch(_client(lambda r: httpx.Response(301, headers={"location": "http://127.0.0.1/"})))
    monkeypatch.setattr(safe_fetch, "MAX_FEED_BYTES", 10)
    with pytest.raises(FeedFetchError, match="larger"):
        adapter.fetch(_client(lambda r: httpx.Response(200, content=RSS)))


def test_source_fetch_parses_a_public_feed_and_keeps_query_params():
    assert [i.title for i in RssFeedAdapter(Source(name="s", feed_url="https://ex.com/feed")).fetch(
        _client(lambda r: httpx.Response(200, content=RSS))
    ).items] == ["One"]

    seen = []
    adapter = OpenFemaAdapter(Source(name="fema", feed_url="https://www.fema.gov/api/open/v1/FemaWebDisasterDeclarations"))
    adapter.fetch(_client(lambda r: seen.append(r) or httpx.Response(200, json={"FemaWebDisasterDeclarations": []})))
    assert "%24top=200" in str(seen[0].url) or "$top=200" in str(seen[0].url)


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


@requires_postgres
def test_admin_token_stops_working_when_account_is_demoted_or_deleted(client, db_session, monkeypatch):
    from app.security import create_admin_access_token

    monkeypatch.setenv("ADMIN_JWT_SECRET", "test-secret")
    user = User(id=uuid.uuid4(), email="editor@example.com", role="ADMIN")
    db_session.add(user)
    db_session.commit()
    token, _ = create_admin_access_token(user.id, user.email, "ADMIN")
    assert client.get("/v1/admin/sources", headers=_auth(token)).status_code == 200

    user.role = None
    db_session.commit()
    assert client.get("/v1/admin/sources", headers=_auth(token)).status_code == 403

    user.role = "ADMIN"
    user.deleted_at = datetime.now(UTC)
    db_session.commit()
    assert client.get("/v1/admin/sources", headers=_auth(token)).status_code == 401


@requires_postgres
def test_admin_principal_carries_the_stored_role_not_the_claim(client, db_session, monkeypatch):
    from app.security import create_admin_access_token

    monkeypatch.setenv("ADMIN_JWT_SECRET", "test-secret")
    user = User(id=uuid.uuid4(), email="ed@example.com", role="EDITOR")
    db_session.add(user)
    db_session.commit()
    token, _ = create_admin_access_token(user.id, user.email, "ADMIN")
    response = client.post(
        "/v1/admin/sources",
        headers=_auth(token),
        json={"name": "Feed", "feed_url": "https://ex.com/feed", "rights_status": "LINK_ONLY"},
    )
    assert response.status_code == 403
    assert "Only an ADMIN" in response.json()["error"]["message"]


@requires_postgres
def test_anonymous_token_must_be_bounded_url_safe(client):
    for bad in ("short", "x" * 129, "has spaces in it ok", "semi;colon-0123456789"):
        assert client.get("/v1/me", headers=_auth(bad)).status_code == 401
    legacy_mobile = "1727712000000-k3j2h1g0f9-a8s7d6f5g4"
    assert client.get("/v1/me", headers=_auth(legacy_mobile)).status_code == 200


@requires_postgres
def test_new_user_creation_is_rate_limited_per_client_but_known_tokens_still_work(client, monkeypatch):
    monkeypatch.setattr(rate_limit, "NEW_USER_MAX_REQUESTS", 2)
    known = str(uuid.uuid4())
    assert client.get("/v1/me", headers=_auth(known)).status_code == 200
    assert client.get("/v1/me", headers=_auth(str(uuid.uuid4()))).status_code == 200

    limited = client.get("/v1/me", headers=_auth(str(uuid.uuid4())))
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert client.get("/v1/me", headers=_auth(known)).status_code == 200
