"""Password hashing, admin JWTs, and login rate limiting (docs/tickets/T05.md).

Rate limiting is a plain Postgres query over `admin_login_attempts` rather
than Redis/in-memory counters, per NON_NEGOTIABLES (no new infra without a
measured need) — admin login volume is far too low to need anything faster.
"""

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt
import pyotp
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AdminLoginAttempt

ADMIN_JWT_ALGORITHM = "HS256"
ADMIN_JWT_EXPIRE_MINUTES = int(os.environ.get("ADMIN_JWT_EXPIRE_MINUTES", "30"))

# ADR-012: a login for an account with no mfa_secret gets this restricted
# scope instead of a full session — just enough time to scan a QR code and
# enter one TOTP code, not a standing credential.
MFA_ENROLLMENT_TOKEN_EXPIRE_MINUTES = 5

# Rate limit: at most this many login attempts (success or failure) per email
# within the window, before further attempts are rejected outright.
LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 5
LOGIN_RATE_LIMIT_WINDOW = timedelta(minutes=15)


def _jwt_secret() -> str:
    secret = os.environ.get("ADMIN_JWT_SECRET")
    if not secret:
        raise RuntimeError("ADMIN_JWT_SECRET is not set")
    return secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_admin_access_token(user_id: UUID, email: str, role: str) -> tuple[str, int]:
    expires_in = ADMIN_JWT_EXPIRE_MINUTES * 60
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "scope": "full",
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, _jwt_secret(), algorithm=ADMIN_JWT_ALGORITHM)
    return token, expires_in


def create_admin_enrollment_token(user_id: UUID, email: str, role: str) -> tuple[str, int]:
    """ADR-012: issued instead of a full session token when an EDITOR/ADMIN
    account with no `mfa_secret` logs in. Only `current_admin_for_enrollment`
    (guarding `/mfa/setup` and `/mfa/enroll`) accepts this scope."""
    expires_in = MFA_ENROLLMENT_TOKEN_EXPIRE_MINUTES * 60
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "scope": "mfa_enrollment",
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, _jwt_secret(), algorithm=ADMIN_JWT_ALGORITHM)
    return token, expires_in


def decode_admin_access_token(token: str) -> dict:
    return jwt.decode(token, _jwt_secret(), algorithms=[ADMIN_JWT_ALGORITHM])


def is_login_rate_limited(db: Session, email: str) -> bool:
    window_start = datetime.now(UTC) - LOGIN_RATE_LIMIT_WINDOW
    count = db.scalar(
        select(func.count())
        .select_from(AdminLoginAttempt)
        .where(AdminLoginAttempt.email == email, AdminLoginAttempt.created_at >= window_start)
    )
    return count >= LOGIN_RATE_LIMIT_MAX_ATTEMPTS


def record_login_attempt(db: Session, email: str, ip: str | None, success: bool) -> None:
    db.add(AdminLoginAttempt(email=email, ip=ip, success=success))
    db.commit()


# --- MFA (T19 §16 baseline: MFA on admin sessions) ---
#
# `users.mfa_secret` (present in the T03 schema, unused until now) is the
# TOTP shared secret. Its presence *is* "MFA enabled" for that admin — there
# is no separate enabled flag, so `/mfa/setup` deliberately does not persist
# the secret it generates until `/mfa/enroll` proves the admin's
# authenticator app actually has it (see app/routers/admin_auth.py), to
# avoid a half-configured admin locking themselves out on next login.
#
# The column stores `encrypt_mfa_secret`'s ciphertext, never the raw TOTP
# secret (P0-2: an unencrypted `infra/scripts/backup.sh` dump — the default
# unless BACKUP_AGE_RECIPIENT is set — would otherwise hand out a permanent
# MFA bypass for every admin to anyone who reads the dump file). Callers
# decrypt with `decrypt_mfa_secret` immediately before `verify_mfa_code`.

MFA_ISSUER = "TTE Admin"


def generate_mfa_secret() -> str:
    return pyotp.random_base32()


def mfa_provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=MFA_ISSUER)


def verify_mfa_code(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def _mfa_encryption_key() -> bytes:
    key = os.environ.get("MFA_SECRET_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("MFA_SECRET_ENCRYPTION_KEY is not set")
    return key.encode("utf-8")


def encrypt_mfa_secret(secret: str) -> str:
    return Fernet(_mfa_encryption_key()).encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_mfa_secret(ciphertext: str) -> str:
    try:
        return Fernet(_mfa_encryption_key()).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError(
            "Stored MFA secret could not be decrypted — wrong or rotated MFA_SECRET_ENCRYPTION_KEY?"
        ) from exc
