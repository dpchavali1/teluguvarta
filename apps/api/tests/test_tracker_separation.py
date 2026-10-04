"""ADR-046 §1: a tracker entry is approved by a different admin than its author."""

from datetime import UTC, datetime, timedelta

import pytest

from tests.conftest import requires_postgres
from tests.test_editorial_workflow import _auth, _token
from tests.test_exam_deadlines import SRC
from tests.test_visa_bulletin import URL, _entry


@pytest.fixture(autouse=True)
def _strict(monkeypatch):
    monkeypatch.delenv("ALLOW_SELF_APPROVAL", raising=False)


@requires_postgres
def test_visa_bulletin_needs_second_admin(client, db_session, monkeypatch):
    author = _token(client, db_session, email="a@example.com")
    other = _token(client, db_session, email="b@example.com")
    body = {"source_url": URL, "entries": [_entry("2013-01-01")]}
    assert client.put("/v1/admin/visa-bulletins/2026-10", json=body, headers=_auth(author)).status_code == 200

    own = client.post("/v1/admin/visa-bulletins/2026-10/approve", headers=_auth(author))
    assert (own.status_code, own.json()["error"]["code"]) == (409, "SELF_APPROVAL_FORBIDDEN")
    assert client.get("/v1/visa-bulletins/latest").status_code == 404

    assert client.post("/v1/admin/visa-bulletins/2026-10/approve", headers=_auth(other)).json()["status"] == "APPROVED"

    # Explicit single-admin override.
    monkeypatch.setenv("ALLOW_SELF_APPROVAL", "true")
    client.put("/v1/admin/visa-bulletins/2026-11", json=body, headers=_auth(author))
    assert client.post("/v1/admin/visa-bulletins/2026-11/approve", headers=_auth(author)).status_code == 200


@requires_postgres
def test_exam_deadline_needs_second_admin(client, db_session):
    author = _token(client, db_session, email="a@example.com")
    other = _token(client, db_session, email="b@example.com")
    body = {"exam": "gre", "kind": "EXAM_DATE", "title": "GRE", "deadline": str((datetime.now(UTC) + timedelta(days=30)).date()), "source_url": SRC}
    item = client.post("/v1/admin/exam-deadlines", json=body, headers=_auth(author)).json()

    own = client.post(f"/v1/admin/exam-deadlines/{item['id']}/approve", headers=_auth(author))
    assert (own.status_code, own.json()["error"]["code"]) == (409, "SELF_APPROVAL_FORBIDDEN")
    assert client.post(f"/v1/admin/exam-deadlines/{item['id']}/approve", headers=_auth(other)).json()["status"] == "APPROVED"
