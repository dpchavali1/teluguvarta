"""Reset an admin user's password (and optionally change its email). MFA is left as is.

Run inside the api container, e.g. on the VPS:
    docker compose -f infra/deploy/docker-compose.prod.yml --env-file .env.prod run --rm \
      -v "$PWD/infra/scripts:/srv/infra/scripts:ro" api \
      python /srv/infra/scripts/reset_admin_password.py [--generate] CURRENT_EMAIL [NEW_EMAIL]

The password is read with getpass, so it never lands in shell history. With --generate
a random password is set and printed once instead (nothing to mistype).
"""

import getpass
import os
import secrets
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import User
from app.security import hash_password


def main() -> int:
    args = sys.argv[1:]
    generate = "--generate" in args
    args = [a for a in args if a != "--generate"]
    if len(args) not in (1, 2):
        print(__doc__)
        return 2
    current = args[0].strip().lower()
    new_email = args[1].strip().lower() if len(args) == 2 else None

    with Session(create_engine(os.environ["DATABASE_URL"])) as db:
        user = db.scalar(select(User).where(User.email == current))
        if user is None:
            print(f"No user with email {current}.")
            return 1
        if generate:
            password = secrets.token_urlsafe(15)
        else:
            password = getpass.getpass("New admin password: ")
            if len(password) < 12 or password != getpass.getpass("Repeat it: "):
                print("Passwords differ or are shorter than 12 characters; nothing changed.")
                return 1
        if new_email:
            user.email = new_email
        user.password_hash = hash_password(password)
        db.commit()
        print(f"Updated {user.email} (role {user.role}).")
        if generate:
            print(f"New password (shown once, save it now): {password}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
