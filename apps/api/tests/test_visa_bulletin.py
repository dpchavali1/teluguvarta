"""P07 / ADR-041: visa bulletin tracker — rules, editor entry/approval,
public reads, follows and the one-alert-per-bulletin dispatch."""

import pytest

from app.content.visa_bulletin import (
    entry_errors,
    movement,
    official_source_url,
    valid_cutoff,
)
from app.jobs.notify import run_notification_dispatch
from app.models import UserVisaFollow
from tests.conftest import requires_postgres
from tests.test_editorial_workflow import _auth, _token
from tests.test_notifications import _job
from tests.test_smart_alerts import AUTH, _rows, _user

URL = "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin/2026/visa-bulletin-for-november-2026.html"


def _entry(cutoff, category="EB2", country="INDIA", chart="FINAL_ACTION"):
    return {"chart": chart, "category": category, "country": country, "cutoff": cutoff}


def test_cutoff_validation_and_movement():
    assert [valid_cutoff(v) for v in ("C", "U", "2013-01-15", "2013-1-5", "soon", "")] == [True, True, True, False, False, False]
    assert movement(None, "2013-01-01") == "NEW"
    assert movement("2013-01-01", "2013-01-01") == "SAME"
    assert movement("2013-01-01", "2013-03-01") == "FORWARD"
    assert movement("2013-03-01", "2013-01-01") == "BACKWARD"
    assert movement("2013-03-01", "C") == "FORWARD"
    assert movement("C", "U") == "BACKWARD"
    assert movement("U", "2013-03-01") == "FORWARD"
    assert entry_errors("FINAL_ACTION", "EB2", "INDIA", "C") is None
    assert entry_errors("X", "EB2", "INDIA", "C") and entry_errors("FINAL_ACTION", "EB9", "INDIA", "C")
    assert entry_errors("FINAL_ACTION", "EB2", "NARNIA", "C") and entry_errors("FINAL_ACTION", "EB2", "INDIA", "later")


@pytest.mark.parametrize("url,ok", [
    (URL, True),
    ("https://evil.example/travel.state.gov", False),
    ("http://travel.state.gov/x", False),
    ("https://travel.state.gov.evil.example/x", False),
])
def test_only_https_state_department_links(url, ok):
    assert official_source_url(url) is ok


@requires_postgres
def test_editor_draft_then_approve_publishes_with_movement(client, db_session):
    token = _token(client, db_session)
    put = lambda month, cutoff, **kw: client.put(
        f"/v1/admin/visa-bulletins/{month}", json={"source_url": URL, "entries": [_entry(cutoff)]}, headers=_auth(token), **kw
    )
    assert client.get("/v1/visa-bulletins/latest").status_code == 404

    bad = client.put("/v1/admin/visa-bulletins/2026-10", json={"source_url": "https://x.example", "entries": [_entry("C")]}, headers=_auth(token))
    assert bad.json()["error"]["code"] == "SOURCE_NOT_OFFICIAL"
    assert client.put("/v1/admin/visa-bulletins/2026-13", json={"source_url": URL, "entries": [_entry("C")]}, headers=_auth(token)).status_code == 422

    assert put("2026-10", "2013-01-01").status_code == 200
    assert client.get("/v1/visa-bulletins/latest").status_code == 404  # drafts are not public
    assert put("2026-10", "2013-02-01").json()["entries"][0]["cutoff"] == "2013-02-01"  # drafts are replaceable
    assert client.post("/v1/admin/visa-bulletins/2026-10/approve", headers=_auth(token)).json()["status"] == "APPROVED"
    assert put("2026-10", "2013-03-01").status_code == 409

    put("2026-11", "2013-06-01")
    client.post("/v1/admin/visa-bulletins/2026-11/approve", headers=_auth(token))
    latest = client.get("/v1/visa-bulletins/latest").json()
    assert latest["month"] == "2026-11"
    assert latest["entries"][0] | {"previous": "2013-02-01"} == latest["entries"][0]
    assert latest["entries"][0]["movement"] == "FORWARD"
    assert client.get("/v1/visa-bulletins/latest", params={"category": "EB1"}).json()["entries"] == []


@requires_postgres
def test_visa_follow_sync_drops_unknown_dedupes_and_caps(client):
    follows = [{"category": "EB2", "country": "INDIA", "alerts": True}, {"category": "EB2", "country": "INDIA"},
               {"category": "EB9", "country": "INDIA"}, {"category": "F2A", "country": "NARNIA"}]
    body = client.patch("/v1/me/preferences", json={"follow_visa": follows}, headers=AUTH).json()
    assert body["follow_visa"] == [{"category": "EB2", "country": "INDIA", "alerts": True}]
    assert client.patch("/v1/me/preferences", json={"max_alerts_per_day": 3}, headers=AUTH).json()["follow_visa"]
    assert client.patch("/v1/me/preferences", json={"follow_visa": []}, headers=AUTH).json()["follow_visa"] == []
    too_many = [{"category": "EB1", "country": "ALL"}] * 6
    assert client.patch("/v1/me/preferences", json={"follow_visa": too_many}, headers=AUTH).status_code == 422


@requires_postgres
def test_approval_alerts_only_changed_alert_followers_once(client, db_session):
    token = _token(client, db_session)
    moved, same, muted, other = (_user(db_session) for _ in range(4))
    db_session.add_all([
        UserVisaFollow(user_id=moved.id, category="EB2", country="INDIA", alerts=True),
        UserVisaFollow(user_id=same.id, category="EB1", country="ALL", alerts=True),
        UserVisaFollow(user_id=muted.id, category="EB2", country="INDIA", alerts=False),
        UserVisaFollow(user_id=other.id, category="F1", country="ALL", alerts=True),
    ])
    db_session.commit()

    def month(m, eb2, eb1):
        entries = [_entry(eb2), _entry(eb1, category="EB1", country="ALL"), _entry("C", category="F1", country="ALL")]
        client.put(f"/v1/admin/visa-bulletins/{m}", json={"source_url": URL, "entries": entries}, headers=_auth(token))
        client.post(f"/v1/admin/visa-bulletins/{m}/approve", headers=_auth(token))

    month("2026-10", "2013-01-01", "C")
    run_notification_dispatch(db_session, _job())
    assert _rows(db_session, moved, "TRACKER_UPDATE") == []  # first bulletin is a baseline

    month("2026-11", "2012-06-01", "C")  # EB2 India retrogressed
    client.post("/v1/admin/visa-bulletins/2026-11/approve", headers=_auth(token))  # re-approve is a no-op
    run_notification_dispatch(db_session, _job())
    run_notification_dispatch(db_session, _job())

    rows = _rows(db_session, moved, "TRACKER_UPDATE")
    assert len(rows) == 1 and rows[0].story_id is None
    for user in (same, muted, other):
        assert _rows(db_session, user, "TRACKER_UPDATE") == []
