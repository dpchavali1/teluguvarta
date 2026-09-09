"""T04 acceptance tests: every §13 endpoint exists, the OpenAPI schema is
valid, and failures return the standard error envelope everywhere.

T14 wired the public endpoints to real Postgres data, so the endpoint-level
tests below need a reachable server (schema-only tests don't).
"""

import pytest
from fastapi.testclient import TestClient
from openapi_spec_validator import validate

from app.main import app
from tests.conftest import requires_postgres

EXPECTED_ENDPOINTS = [
    ("GET", "/v1/home"),
    ("GET", "/v1/stories"),
    ("GET", "/v1/stories/{slug}"),
    ("GET", "/v1/topics/{slug}"),
    ("GET", "/v1/search"),
    ("GET", "/v1/config"),
    ("GET", "/v1/stories/{slug}/share-meta"),
    ("GET", "/v1/me"),
    ("PATCH", "/v1/me/preferences"),
    ("POST", "/v1/me/saved/{story_id}"),
    ("DELETE", "/v1/me/saved/{story_id}"),
    ("POST", "/v1/me/push-tokens"),
    ("DELETE", "/v1/me/account"),
    ("POST", "/v1/admin/auth/login"),
    ("GET", "/v1/admin/sources"),
    ("PATCH", "/v1/admin/sources/{id}"),
    ("GET", "/v1/admin/review-queue"),
    ("POST", "/v1/admin/stories/{id}/approve"),
    ("POST", "/v1/admin/stories/{id}/reject"),
    ("POST", "/v1/admin/stories/{id}/retract"),
    ("POST", "/v1/admin/stories/{id}/correct"),
    ("GET", "/v1/admin/jobs"),
    ("GET", "/v1/admin/audit"),
]


def test_openapi_schema_is_valid():
    schema = app.openapi()
    validate(schema)


def test_every_spec_endpoint_is_registered():
    schema = app.openapi()
    registered = {
        (method.upper(), path)
        for path, methods in schema["paths"].items()
        for method in methods
    }
    for method, templated_path in EXPECTED_ENDPOINTS:
        # §13 uses {id}, our routes use the entity-specific param name —
        # compare by segment count/prefix rather than the literal template.
        path = templated_path.replace("{id}", "{source_id}") if "sources/{id}" in templated_path else templated_path
        path = path.replace("{id}", "{story_id}") if "stories/{id}" in path else path
        assert (method, path) in registered, f"missing {method} {templated_path}"


@pytest.fixture
def client(migrated_database):
    from app.db import _engine_for

    _engine_for.cache_clear()
    yield TestClient(app)
    _engine_for.cache_clear()


pytestmark = requires_postgres


def test_error_envelope_on_not_found(client):
    response = client.get("/v1/stories/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert set(body["error"].keys()) == {"code", "message", "request_id"}
    assert body["error"]["code"] == "STORY_NOT_FOUND"


def test_error_envelope_on_unauthenticated(client):
    response = client.get("/v1/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_error_envelope_on_validation_error(client):
    response = client.get("/v1/search")  # missing required `q`
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_authenticated_endpoint_succeeds_with_bearer_token(client):
    response = client.get("/v1/me", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert "id" in response.json()


def test_admin_endpoint_requires_auth(client):
    response = client.get("/v1/admin/sources")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_public_endpoints_need_no_auth(client):
    assert client.get("/v1/home").status_code == 200
    assert client.get("/v1/stories").status_code == 200
    assert client.get("/v1/config").status_code == 200
