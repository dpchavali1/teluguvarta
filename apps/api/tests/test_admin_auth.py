"""T05 acceptance tests: admin login, RBAC on /v1/admin/*, and rate limiting;
ADR-012 MFA enrollment; ADR-028 cookie sessions (review 2026-09-30 R11).

Needs real Postgres (a seeded user, real login attempts) so these use the
same `migrated_database` fixture as the T03 schema tests, and skip the same
way when no Postgres is reachable.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tests.admin_session_helpers import admin_auth, admin_session_token
from tests.conftest import requires_postgres

pytestmark = requires_postgres

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "correct horse battery staple"
CSRF = {"X-TTE-Admin": "1"}


@pytest.fixture
def client(migrated_database, monkeypatch):
    monkeypatch.setenv("ADMIN_JWT_SECRET", "test-secret")
    monkeypatch.setenv("MFA_SECRET_ENCRYPTION_KEY", "sAIUJOCgoJ0pmobLNaO-_x_0R49CtpXyRDJ0iemFN9g=")

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


def _seed_admin(db_session, *, email=ADMIN_EMAIL, password=ADMIN_PASSWORD, role="ADMIN"):
    from app.models import User
    from app.security import hash_password

    user = User(id=uuid.uuid4(), email=email, role=role, password_hash=hash_password(password))
    db_session.add(user)
    db_session.commit()
    return user


_CLOCK = {"t": 1_800_000_000.0}


@pytest.fixture(autouse=True)
def _fake_mfa_clock(monkeypatch):
    # ADR-046 §5: a TOTP code is single-use, so each code the tests mint must
    # belong to a later 30 s step than the last one the server accepted.
    from app import security

    monkeypatch.setattr(security, "_mfa_now", lambda: datetime.fromtimestamp(_CLOCK["t"], UTC))


def _code(secret: str) -> str:
    import pyotp

    _CLOCK["t"] += 30
    return pyotp.TOTP(secret).at(_CLOCK["t"])


def _login(client, *, email=ADMIN_EMAIL, password=ADMIN_PASSWORD, mfa_code=None, headers=None):
    body = {"email": email, "password": password}
    if mfa_code is not None:
        body["mfa_code"] = mfa_code
    return client.post("/v1/admin/auth/login", json=body, headers={**CSRF, **(headers or {})})


def _session_cookie(response) -> tuple[str, str]:
    """(value, full Set-Cookie header) of the `tte_admin` cookie on a response."""
    header = next(h for h in response.headers.get_list("set-cookie") if h.startswith("tte_admin="))
    return header.split(";", 1)[0].removeprefix("tte_admin="), header


def _login_token(client, **kwargs) -> str:
    response = _login(client, **kwargs)
    assert response.status_code == 200, response.text
    return _session_cookie(response)[0]


def _enrolled_admin(db_session):
    from app.security import encrypt_mfa_secret, generate_mfa_secret

    secret = generate_mfa_secret()
    user = _seed_admin(db_session)
    user.mfa_secret = encrypt_mfa_secret(secret)
    db_session.commit()
    return user, secret


def test_login_sets_an_httponly_session_cookie_that_grants_admin_access(client, db_session):
    # ADR-012: an account with mfa_secret already set gets a full session
    # immediately — the no-MFA-yet case is covered separately below.

    from app.models import AdminSession

    user, secret = _enrolled_admin(db_session)

    response = _login(client, mfa_code=_code(secret))
    assert response.status_code == 200
    body = response.json()
    assert body == {"expires_in": 12 * 3600, "role": "ADMIN", "mfa_enrollment_required": False}

    token, header = _session_cookie(response)
    attributes = {part.strip().lower() for part in header.split(";")[1:]}
    assert {"httponly", "secure", "samesite=strict", "path=/v1/admin"} <= attributes
    assert not any(a.startswith("domain=") for a in attributes)  # host-only on the API

    # Only the hash is stored: a database read can't be replayed as a cookie.
    row = db_session.query(AdminSession).filter_by(user_id=user.id).one()
    assert row.token_hash != token and token not in row.token_hash

    assert client.get("/v1/admin/sources", headers=admin_auth(token)).status_code == 200
    session = client.get("/v1/admin/auth/session", headers=admin_auth(token)).json()
    assert session["email"] == ADMIN_EMAIL and session["role"] == "ADMIN"
    assert session["mfa_enrollment_required"] is False


def test_bearer_tokens_are_no_longer_accepted(client, db_session):
    token = admin_session_token(db_session, _seed_admin(db_session).id)
    response = client.get("/v1/admin/sources", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert client.get("/v1/admin/sources").status_code == 401


def test_state_changing_requests_need_the_csrf_header(client, db_session):
    user = _seed_admin(db_session)
    token = admin_session_token(db_session, user.id)
    cookie_only = {"Cookie": f"tte_admin={token}"}

    # Reads don't need it...
    assert client.get("/v1/admin/sources", headers=cookie_only).status_code == 200
    # ...writes do, including login itself (login CSRF).
    response = client.post(
        "/v1/admin/sources",
        headers=cookie_only,
        json={"name": "Feed", "feed_url": "https://ex.com/feed", "rights_status": "LINK_ONLY"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_HEADER_REQUIRED"
    no_header_login = client.post("/v1/admin/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert no_header_login.status_code == 403
    assert client.post("/v1/admin/auth/logout", headers=cookie_only).status_code == 403


def test_session_ends_after_idle_and_absolute_timeouts(client, db_session):
    from app.models import AdminSession

    user = _seed_admin(db_session)
    idle = admin_session_token(db_session, user.id)
    absolute = admin_session_token(db_session, user.id)
    rows = {row.id: row for row in db_session.query(AdminSession).filter_by(user_id=user.id)}
    now = datetime.now(UTC)
    first, second = sorted(rows.values(), key=lambda r: r.created_at)
    first.last_seen_at = now - timedelta(minutes=31)
    second.created_at = now - timedelta(hours=12, minutes=1)
    second.expires_at = now - timedelta(minutes=1)
    db_session.commit()

    assert client.get("/v1/admin/sources", headers=admin_auth(idle)).status_code == 401
    assert client.get("/v1/admin/sources", headers=admin_auth(absolute)).status_code == 401


def test_requests_keep_an_active_session_alive(client, db_session):
    from app.models import AdminSession

    user = _seed_admin(db_session)
    token = admin_session_token(db_session, user.id)
    row = db_session.query(AdminSession).filter_by(user_id=user.id).one()
    row.last_seen_at = datetime.now(UTC) - timedelta(minutes=29)
    db_session.commit()

    assert client.get("/v1/admin/sources", headers=admin_auth(token)).status_code == 200
    db_session.expire_all()
    assert datetime.now(UTC) - row.last_seen_at < timedelta(minutes=1)


def test_logout_revokes_only_this_session(client, db_session):
    user = _seed_admin(db_session)
    this = admin_session_token(db_session, user.id)
    other = admin_session_token(db_session, user.id)

    listed = client.get("/v1/admin/auth/sessions", headers=admin_auth(this)).json()["items"]
    assert len(listed) == 2
    assert [item["current"] for item in listed].count(True) == 1

    response = client.post("/v1/admin/auth/logout", headers=admin_auth(this))
    assert response.status_code == 204
    _, header = _session_cookie(response)
    assert "max-age=0" in header.lower()

    assert client.get("/v1/admin/sources", headers=admin_auth(this)).status_code == 401
    assert client.get("/v1/admin/sources", headers=admin_auth(other)).status_code == 200


def test_logout_everywhere_revokes_every_session_of_the_account(client, db_session):
    user = _seed_admin(db_session)
    colleague = _seed_admin(db_session, email="colleague@example.com")
    this = admin_session_token(db_session, user.id)
    other = admin_session_token(db_session, user.id)
    theirs = admin_session_token(db_session, colleague.id)

    assert client.post("/v1/admin/auth/logout-everywhere", headers=admin_auth(this)).status_code == 204
    assert client.get("/v1/admin/sources", headers=admin_auth(this)).status_code == 401
    assert client.get("/v1/admin/sources", headers=admin_auth(other)).status_code == 401
    assert client.get("/v1/admin/sources", headers=admin_auth(theirs)).status_code == 200


def test_signing_in_again_ends_the_previous_session(client, db_session):

    _, secret = _enrolled_admin(db_session)
    first = _login_token(client, mfa_code=_code(secret))
    second = _login_token(client, mfa_code=_code(secret), headers={"Cookie": f"tte_admin={first}"})

    assert client.get("/v1/admin/sources", headers=admin_auth(first)).status_code == 401
    assert client.get("/v1/admin/sources", headers=admin_auth(second)).status_code == 200


def test_cleanup_deletes_sessions_that_ended_over_30_days_ago(db_session):
    from app.admin_sessions import purge_ended_sessions
    from app.models import AdminSession

    user = _seed_admin(db_session)
    for _ in range(3):
        admin_session_token(db_session, user.id)
    old_revoked, old_expired, live = db_session.query(AdminSession).filter_by(user_id=user.id).all()
    now = datetime.now(UTC)
    old_revoked.revoked_at = now - timedelta(days=31)
    old_expired.expires_at = now - timedelta(days=31)
    db_session.commit()

    assert purge_ended_sessions(db_session, now) == 2
    assert [row.id for row in db_session.query(AdminSession).filter_by(user_id=user.id)] == [live.id]


def test_login_rejects_wrong_password(client, db_session):
    _seed_admin(db_session)

    response = _login(client, password="wrong")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert not response.headers.get_list("set-cookie")


def test_login_rejects_unknown_email(client, db_session):
    response = _login(client, email="nobody@example.com", password="whatever")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_non_staff_user_session_cannot_reach_admin(client, db_session):
    # An ordinary user (no role) gets 403 even with a session row, and the
    # check revokes it.
    user = _seed_admin(db_session, role=None)
    token = admin_session_token(db_session, user.id)

    response = client.get("/v1/admin/sources", headers=admin_auth(token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_login_is_rate_limited_after_n_attempts(client, db_session):
    from app.models import AdminLoginAttempt

    _seed_admin(db_session)

    # Fast-forward past the attempt count without waiting on real wall-clock
    # time or firing five real HTTP requests: insert the attempt history the
    # rate limiter reads directly.
    now = datetime.now(UTC)
    for _ in range(5):
        db_session.add(AdminLoginAttempt(email=ADMIN_EMAIL, ip="127.0.0.1", success=False, created_at=now))
    db_session.commit()

    response = _login(client)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"


def test_login_rate_limit_does_not_affect_other_emails(client, db_session):
    from app.models import AdminLoginAttempt

    _seed_admin(db_session)
    _seed_admin(db_session, email="other-admin@example.com")

    now = datetime.now(UTC)
    for _ in range(5):
        db_session.add(AdminLoginAttempt(email=ADMIN_EMAIL, ip="127.0.0.1", success=False, created_at=now))
    db_session.commit()

    assert _login(client, email="other-admin@example.com").status_code == 200


def test_login_is_rate_limited_per_ip_across_emails(client, db_session):
    from app.models import AdminLoginAttempt

    _seed_admin(db_session)

    # 20 failures from one address against 20 different (even unknown) emails:
    # no single email reaches its own limit, but the address is blocked.
    now = datetime.now(UTC)
    for i in range(20):
        db_session.add(AdminLoginAttempt(email=f"guess{i}@example.com", ip="testclient", success=False, created_at=now))
    db_session.commit()

    response = _login(client)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"


def test_successful_logins_do_not_count_toward_the_ip_limit(client, db_session):
    from app.models import AdminLoginAttempt

    _seed_admin(db_session)
    now = datetime.now(UTC)
    for i in range(25):
        db_session.add(AdminLoginAttempt(email=f"ok{i}@example.com", ip="testclient", success=True, created_at=now))
    db_session.commit()

    assert _login(client).status_code == 200


# --- T19 §16 baseline: MFA on admin sessions ---


def test_login_without_mfa_enrolled_ignores_mfa_code_field(client, db_session):
    _seed_admin(db_session)
    response = _login(client, mfa_code="123456")
    assert response.status_code == 200


# --- P0-3 / ADR-012: first-login MFA enrollment flow ---


def test_login_without_mfa_secret_issues_enrollment_scoped_session(client, db_session):
    _seed_admin(db_session)

    response = _login(client)
    assert response.status_code == 200
    assert response.json()["mfa_enrollment_required"] is True
    assert response.json()["expires_in"] == 5 * 60
    headers = admin_auth(_session_cookie(response)[0])

    # The enrollment session can reach the enrollment endpoints and /session...
    assert client.post("/v1/admin/auth/mfa/setup", headers=headers).status_code == 200
    assert client.get("/v1/admin/auth/session", headers=headers).json()["mfa_enrollment_required"] is True

    # ...but not any other admin route, and not even MFA status/disable.
    sources = client.get("/v1/admin/sources", headers=headers)
    assert sources.status_code == 403
    assert sources.json()["error"]["code"] == "MFA_ENROLLMENT_REQUIRED"

    status = client.get("/v1/admin/auth/mfa", headers=headers)
    assert status.status_code == 403
    assert status.json()["error"]["code"] == "MFA_ENROLLMENT_REQUIRED"


def test_completed_enrollment_ends_that_session_and_next_login_is_full(client, db_session):

    _seed_admin(db_session)
    headers = admin_auth(_login_token(client))

    secret = client.post("/v1/admin/auth/mfa/setup", headers=headers).json()["secret"]
    enroll = client.post(
        "/v1/admin/auth/mfa/enroll", json={"secret": secret, "code": _code(secret)}, headers=headers
    )
    assert enroll.status_code == 200
    assert "max-age=0" in _session_cookie(enroll)[1].lower()
    assert client.get("/v1/admin/auth/session", headers=headers).status_code == 401

    login_response = _login(client, mfa_code=_code(secret))
    assert login_response.status_code == 200
    assert login_response.json()["mfa_enrollment_required"] is False

    full = admin_auth(_session_cookie(login_response)[0])
    assert client.get("/v1/admin/sources", headers=full).status_code == 200


def test_mfa_enroll_requires_valid_code_then_login_requires_it(client, db_session):

    _seed_admin(db_session)
    headers = admin_auth(_login_token(client))

    setup = client.post("/v1/admin/auth/mfa/setup", headers=headers)
    assert setup.status_code == 200
    secret = setup.json()["secret"]

    bad_enroll = client.post("/v1/admin/auth/mfa/enroll", json={"secret": secret, "code": "000000"}, headers=headers)
    assert bad_enroll.status_code == 401
    assert bad_enroll.json()["error"]["code"] == "INVALID_MFA_CODE"

    good_code = _code(secret)
    enroll = client.post("/v1/admin/auth/mfa/enroll", json={"secret": secret, "code": good_code}, headers=headers)
    assert enroll.status_code == 200
    assert enroll.json()["enabled"] is True

    # A fresh, MFA-verified login is required for a full session (ADR-012).
    full_headers = admin_auth(_login_token(client, mfa_code=_code(secret)))
    status = client.get("/v1/admin/auth/mfa", headers=full_headers)
    assert status.json()["enabled"] is True

    # Password alone is no longer enough.
    no_code = _login(client)
    assert no_code.status_code == 401
    assert no_code.json()["error"]["code"] == "MFA_REQUIRED"

    wrong_code = _login(client, mfa_code="000000")
    assert wrong_code.status_code == 401
    assert wrong_code.json()["error"]["code"] == "INVALID_MFA_CODE"

    right_code = _login(client, mfa_code=_code(secret))
    assert right_code.status_code == 200


def test_mfa_secret_is_encrypted_at_rest(client, db_session):

    from app.models import User
    from app.security import decrypt_mfa_secret

    _seed_admin(db_session)
    headers = admin_auth(_login_token(client))

    secret = client.post("/v1/admin/auth/mfa/setup", headers=headers).json()["secret"]
    good_code = _code(secret)
    client.post("/v1/admin/auth/mfa/enroll", json={"secret": secret, "code": good_code}, headers=headers)

    db_session.expire_all()
    stored = db_session.query(User).filter_by(email=ADMIN_EMAIL).one().mfa_secret
    assert stored != secret
    assert decrypt_mfa_secret(stored) == secret


def test_mfa_disable_requires_current_code(client, db_session):

    _, secret = _enrolled_admin(db_session)
    headers = admin_auth(_login_token(client, mfa_code=_code(secret)))

    wrong = client.request("DELETE", "/v1/admin/auth/mfa", json={"code": "000000"}, headers=headers)
    assert wrong.status_code == 401

    right = client.request("DELETE", "/v1/admin/auth/mfa", json={"code": _code(secret)}, headers=headers)
    assert right.status_code == 200
    assert right.json()["enabled"] is False

    # MFA no longer required.
    assert _login(client).status_code == 200


def test_enrolled_admin_cannot_replace_authenticator(client, db_session):
    import pyotp

    _seed_admin(db_session)
    headers = admin_auth(_login_token(client))
    secret = client.post("/v1/admin/auth/mfa/setup", headers=headers).json()["secret"]
    client.post("/v1/admin/auth/mfa/enroll", json={"secret": secret, "code": _code(secret)}, headers=headers)

    full = admin_auth(_login_token(client, mfa_code=_code(secret)))
    other = pyotp.random_base32()
    again = client.post("/v1/admin/auth/mfa/enroll", json={"secret": other, "code": _code(other)}, headers=full)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "MFA_ALREADY_ENROLLED"


def test_a_totp_code_cannot_be_used_twice(client, db_session):
    _, secret = _enrolled_admin(db_session)
    code = _code(secret)

    assert _login(client, mfa_code=code).status_code == 200
    replay = _login(client, mfa_code=code)
    assert (replay.status_code, replay.json()["error"]["code"]) == (401, "INVALID_MFA_CODE")

    # An earlier step than the last accepted one is also refused (no going back).
    import pyotp

    older = pyotp.TOTP(secret).at(_CLOCK["t"] - 30)
    assert _login(client, mfa_code=older).status_code == 401
    assert _login(client, mfa_code=_code(secret)).status_code == 200


def test_disabling_mfa_clears_the_replay_marker(client, db_session):
    from app.models import User

    user, secret = _enrolled_admin(db_session)
    headers = admin_auth(_login_token(client, mfa_code=_code(secret)))
    assert client.request("DELETE", "/v1/admin/auth/mfa", json={"code": _code(secret)}, headers=headers).status_code == 200
    db_session.expire_all()
    assert db_session.get(User, user.id).mfa_last_step is None


def test_operator_mfa_reset_script_clears_mfa_and_signs_out(client, db_session, migrated_database, monkeypatch):
    import importlib.util
    import sys
    from pathlib import Path

    from app.models import AuditEvent, User

    user, secret = _enrolled_admin(db_session)
    token = _login_token(client, mfa_code=_code(secret))

    path = Path(__file__).resolve().parents[3] / "infra" / "scripts" / "reset_admin_mfa.py"
    spec = importlib.util.spec_from_file_location("reset_admin_mfa", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("DATABASE_URL", migrated_database)
    monkeypatch.setattr(sys, "argv", ["reset_admin_mfa.py", ADMIN_EMAIL.upper()])
    assert module.main() == 0

    db_session.expire_all()
    assert db_session.get(User, user.id).mfa_secret is None
    assert db_session.query(AuditEvent).filter_by(action="ADMIN_MFA_RESET", entity_id=user.id).count() == 1
    assert client.get("/v1/admin/auth/mfa", headers=admin_auth(token)).status_code == 401
    # Password still works, and with no authenticator the account lands in enrollment, not a full session.
    assert _login(client).status_code == 200
