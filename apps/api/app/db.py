"""SQLAlchemy session wiring.

Reads `DATABASE_URL` lazily (per request, cached per URL) rather than once at
import time, so tests can point different requests at different throw-away
databases via `monkeypatch.setenv` before the app is exercised.
"""

import os
from collections.abc import Iterator
from functools import cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


@cache
def _engine_for(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True)


def get_db() -> Iterator[Session]:
    url = os.environ["DATABASE_URL"]
    session_factory = sessionmaker(bind=_engine_for(url))
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
