"""Reset an admin user's MFA after a lost authenticator (ADR-046 section 5).

Clears the enrolled authenticator and signs the account out everywhere. The
password is untouched; the next sign-in lands in the restricted enrollment
session (ADR-012) and must enrol a new authenticator. Operator-only: there is
deliberately no self-service path.

Run inside the api container, e.g. on the VPS:
    docker compose -f infra/deploy/docker-compose.prod.yml --env-file .env.prod run --rm \
      -v "$PWD/infra/scripts:/srv/infra/scripts:ro" api \
      python /srv/infra/scripts/reset_admin_mfa.py ADMIN_EMAIL
"""

import os
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.admin_sessions import revoke_all_for_user
from app.models import AuditEvent, User


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    email = sys.argv[1].strip().lower()
    with Session(create_engine(os.environ["DATABASE_URL"])) as db:
        user = db.scalar(select(User).where(User.email == email, User.role.is_not(None)))
        if user is None:
            print(f"No admin with email {email}.")
            return 1
        had_mfa = user.mfa_secret is not None
        user.mfa_secret = None
        user.mfa_last_step = None
        revoked = revoke_all_for_user(db, user.id)
        db.add(AuditEvent(actor="operator", action="ADMIN_MFA_RESET", entity_type="user", entity_id=user.id,
                          metadata_={"had_mfa": had_mfa, "sessions_revoked": revoked}))
        db.commit()
        print(f"MFA reset for {email} (had MFA: {had_mfa}); {revoked} session(s) revoked. Next sign-in must re-enrol.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
