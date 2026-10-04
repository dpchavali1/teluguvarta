"""P07 / ADR-041: exam and deadline reminders — rules, editor entry/approval,
public reads, follows, and the approval and countdown alerts."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app import rate_limit
from app.content.exam_deadline import (
    alert_copy,
    entry_error,
    normalize_exam,
    notification_key,
    parse_notification_key,
    reminder_tag,
)
from app.jobs.notify import run_notification_dispatch
from app.models import UserExamFollow
from tests.conftest import requires_postgres
from tests.test_editorial_workflow import _auth, _token
from tests.test_notifications import _job
from tests.test_smart_alerts import AUTH, _rows, _user

SRC = "https://example.org/official/dates"


@pytest.fixture(autouse=True)
def _fresh_admin_rate_limit():
    # These tests make many admin calls; the in-memory window is shared suite-wide.
    rate_limit._WINDOWS.clear()
    yield
    rate_limit._WINDOWS.clear()


def _body(deadline, exam="gre", kind="REGISTRATION_DEADLINE", title="GRE registration closes"):
    return {"exam": exam, "kind": kind, "title": title, "deadline": str(deadline), "source_url": SRC}


def test_rules():
    assert [normalize_exam(v) for v in (" gre ", "TOEFL-iBT", "x", "bad key", "a" * 21)] == ["GRE", "TOEFL-IBT", None, None, None]
    assert entry_error("GRE", "EXAM_DATE", "t", SRC) is None
    assert all(entry_error(*args) for args in [("x", "EXAM_DATE", "t", SRC), ("GRE", "NOPE", "t", SRC),
                                               ("GRE", "EXAM_DATE", " ", SRC), ("GRE", "EXAM_DATE", "t", "http://x.example/a"),
                                               ("GRE", "EXAM_DATE", "t", "https://ets.org\\@evil.example")])
    today = date(2026, 10, 4)
    assert [reminder_tag(today + timedelta(days=n), today) for n in (0, 1, 2, 7, 8)] == [None, "d1", None, "d7", None]
    assert parse_notification_key(notification_key("abc", "d7")) == ("abc", "d7")
    assert parse_notification_key("visa_bulletin:abc") is None
    assert alert_copy("GRE", "EXAM_DATE", "GRE test", today, "d1")[0] == "GRE: exam date in 1 day"


@requires_postgres
def test_draft_approve_withdraw_and_public_reads(client, db_session):
    token = _token(client, db_session)
    soon = datetime.now(UTC).date() + timedelta(days=30)
    assert client.get("/v1/exam-deadlines").json() == []
    assert client.post("/v1/admin/exam-deadlines", json=_body(soon, kind="NOPE"), headers=_auth(token)).status_code == 422

    made = client.post("/v1/admin/exam-deadlines", json=_body(soon), headers=_auth(token))
    assert made.status_code == 201 and made.json()["status"] == "DRAFT" and made.json()["exam"] == "GRE"
    item_id = made.json()["id"]
    assert client.get("/v1/exam-deadlines").json() == []  # drafts are never public

    edited = client.put(f"/v1/admin/exam-deadlines/{item_id}", json=_body(soon, title="Edited"), headers=_auth(token))
    assert edited.json()["title"] == "Edited"
    approved = client.post(f"/v1/admin/exam-deadlines/{item_id}/approve", headers=_auth(token))
    assert approved.json()["status"] == "APPROVED"
    assert [r["id"] for r in client.get("/v1/exam-deadlines?exam=gre").json()] == [item_id]
    assert client.get("/v1/exam-deadlines?exam=toefl").json() == []
    assert client.put(f"/v1/admin/exam-deadlines/{item_id}", json=_body(soon), headers=_auth(token)).status_code == 409

    client.post(f"/v1/admin/exam-deadlines/{item_id}/withdraw", headers=_auth(token))
    assert client.get("/v1/exam-deadlines").json() == []
    assert client.post(f"/v1/admin/exam-deadlines/{item_id}/approve", headers=_auth(token)).status_code == 409

    past = client.post("/v1/admin/exam-deadlines", json=_body(date(2020, 1, 1)), headers=_auth(token)).json()["id"]
    client.post(f"/v1/admin/exam-deadlines/{past}/approve", headers=_auth(token))
    assert client.get("/v1/exam-deadlines").json() == []  # past dates are not upcoming


@requires_postgres
def test_exam_follow_sync_normalizes_dedupes_and_caps(client):
    follows = [{"exam": "gre", "alerts": True}, {"exam": "GRE"}, {"exam": "bad key"}]
    body = client.patch("/v1/me/preferences", json={"follow_exams": follows}, headers=AUTH).json()
    assert body["follow_exams"] == [{"exam": "GRE", "alerts": True}]
    assert client.patch("/v1/me/preferences", json={"max_alerts_per_day": 3}, headers=AUTH).json()["follow_exams"]
    assert client.patch("/v1/me/preferences", json={"follow_exams": []}, headers=AUTH).json()["follow_exams"] == []
    assert client.patch("/v1/me/preferences", json={"follow_exams": [{"exam": "GRE"}] * 11}, headers=AUTH).status_code == 422


@requires_postgres
def test_approval_and_countdown_alert_only_alert_followers_once(client, db_session):
    token = _token(client, db_session)
    follower, muted, other = (_user(db_session) for _ in range(3))
    db_session.add_all([
        UserExamFollow(user_id=follower.id, exam="GRE", alerts=True),
        UserExamFollow(user_id=muted.id, exam="GRE", alerts=False),
        UserExamFollow(user_id=other.id, exam="TOEFL", alerts=True),
    ])
    db_session.commit()
    in_a_week = datetime.now(UTC).date() + timedelta(days=7)
    item_id = client.post("/v1/admin/exam-deadlines", json=_body(in_a_week), headers=_auth(token)).json()["id"]
    run_notification_dispatch(db_session, _job())
    assert _rows(db_session, follower, "TRACKER_UPDATE") == []  # a draft alerts nobody

    client.post(f"/v1/admin/exam-deadlines/{item_id}/approve", headers=_auth(token))
    client.post(f"/v1/admin/exam-deadlines/{item_id}/approve", headers=_auth(token))  # no-op
    run_notification_dispatch(db_session, _job())
    run_notification_dispatch(db_session, _job())

    keys = sorted(r.notification_key for r in _rows(db_session, follower, "TRACKER_UPDATE"))
    assert keys == [notification_key(item_id, "d7"), notification_key(item_id, "new")]  # approval + 7-day reminder
    for user in (muted, other):
        assert _rows(db_session, user, "TRACKER_UPDATE") == []


@pytest.mark.parametrize("path", ["/v1/admin/exam-deadlines"])
@requires_postgres
def test_admin_routes_require_auth(client, path):
    assert client.get(path).status_code in (401, 403)


@pytest.fixture(autouse=True)
def _single_admin_override(monkeypatch):
    # These journeys use one admin; separation of duties is tested in test_tracker_separation.py.
    monkeypatch.setenv("ALLOW_SELF_APPROVAL", "true")
