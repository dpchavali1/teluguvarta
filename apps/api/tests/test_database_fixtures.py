"""Regression checks for scratch-database isolation and failure cleanup."""

import pytest
from sqlalchemy.engine import make_url

from tests import conftest
from tests.conftest import requires_postgres


@requires_postgres
def test_overlapping_scratch_databases_are_independent():
    first = conftest.scratch_database.__wrapped__()
    second = conftest.scratch_database.__wrapped__()
    try:
        first_url = next(first)
        second_url = next(second)
        assert make_url(first_url).database != make_url(second_url).database
        first.close()
        # Dropping one run must not remove the other's database.
        from sqlalchemy import create_engine, text

        engine = create_engine(second_url)
        try:
            with engine.connect() as conn:
                assert conn.scalar(text("SELECT 1")) == 1
        finally:
            engine.dispose()
    finally:
        first.close()
        second.close()


def test_failed_creation_closes_admin_connection(monkeypatch):
    class Connection:
        closed = False

        def cursor(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, query):
            raise RuntimeError("creation failed")

        def close(self):
            self.closed = True

    connection = Connection()
    monkeypatch.setattr(
        conftest, "_admin_connect",
        lambda: (connection, make_url("postgresql://test@localhost/test")),
    )
    fixture = conftest.scratch_database.__wrapped__()
    with pytest.raises(RuntimeError, match="creation failed"):
        next(fixture)
    assert connection.closed
