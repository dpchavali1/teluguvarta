"""Reset an admin user's password (and optionally change its email). MFA is left as is.

Run inside the api container, e.g. on the VPS:
    docker compose -f infra/deploy/docker-compose.prod.yml --env-file .env.prod run --rm \
      -v "$PWD/infra/scripts:/srv/infra/scripts:ro" api \
      python /srv/infra/scripts/reset_admin_password.py CURRENT_EMAIL [NEW_EMAIL]

The password is read with getpass, so it never lands in shell history.
"""

import getpass
import os
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import User
from app.security import hash_password


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        return 2
    current = sys.argv[1].strip().lower()
    new_email = sys.argv[2].strip().lower() if len(sys.argv) == 3 else None

    with Session(create_engine(os.environ["DATABASE_URL"])) as db:
        user = db.scalar(select(User).where(User.email == current))
        if user is None:
            print(f"No user with email {current}.")
            return 1
        password = getpass.getpass("New admin password: ")
        if len(password) < 12 or password != getpass.getpass("Repeat it: "):
            print("Passwords differ or are shorter than 12 characters; nothing changed.")
            return 1
        if new_email:
            user.email = new_email
        user.password_hash = hash_password(password)
        db.commit()
        print(f"Updated {user.email} (role {user.role}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
