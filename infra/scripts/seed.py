"""Placeholder seed script — run after migrations.

Will seed topics, a handful of LINK_ONLY sources, and test users once T03
(schema) and T06 (source registry) land. Intentionally a no-op until then so
`pnpm run seed` is safe to wire into onboarding docs early.
"""

import os
import sys


def main() -> int:
    if not os.environ.get("DATABASE_URL"):
        print(
            "DATABASE_URL is not set. Copy .env.example to .env and fill it in.",
            file=sys.stderr,
        )
        return 1
    print("No schema yet (T03) — nothing to seed. This is a placeholder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
