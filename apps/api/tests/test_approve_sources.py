"""infra/scripts/approve_sources.py — owner-approved LINK_ONLY sources."""

import importlib.util
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.models import Source

_SCRIPT = (
    Path(__file__).resolve().parents[3] / "infra" / "scripts" / "approve_sources.py"
)
_spec = importlib.util.spec_from_file_location("approve_sources", _SCRIPT)
approve_sources = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(approve_sources)

NOW = datetime(2026, 9, 30, tzinfo=UTC)


def test_every_source_carries_required_rights_evidence():
    for spec in approve_sources.APPROVED_SOURCES:
        assert spec["rights_evidence_url"].startswith("https://")
        assert spec["rights_evidence"]["terms_url"] == spec["rights_evidence_url"]
        assert spec["feed_url"].startswith("https://")


def test_apply_enables_sources_and_deactivates_npr(db_session):
    db_session.add(
        Source(id=uuid.uuid4(), name="NPR News", rights_status="LINK_ONLY", active=True)
    )
    db_session.commit()

    approve_sources.apply(db_session, "owner@example.com", NOW)
    db_session.commit()

    added = db_session.scalars(
        select(Source).where(Source.reviewer == "owner@example.com")
    ).all()
    assert len(added) == len(approve_sources.APPROVED_SOURCES)
    assert all(
        s.rights_status == "LINK_ONLY" and s.active and s.rights_reviewed_at
        for s in added
    )
    assert (
        db_session.scalar(select(Source).where(Source.name == "NPR News")).active
        is False
    )


def test_apply_is_idempotent_and_keeps_original_review(db_session):
    approve_sources.apply(db_session, "owner@example.com", NOW)
    db_session.commit()
    log = approve_sources.apply(
        db_session, "someone-else@example.com", datetime.now(UTC)
    )
    db_session.commit()

    assert all(line.startswith("update ") for line in log)
    count = db_session.scalars(select(Source)).all()
    assert len(count) == len(approve_sources.APPROVED_SOURCES)
    assert {s.reviewer for s in count} == {"owner@example.com"}


def test_apply_never_re_enables_a_disabled_source(db_session):
    db_session.add(
        Source(
            id=uuid.uuid4(), name="NTV Telugu", rights_status="DISABLED", active=False
        )
    )
    db_session.commit()

    log = approve_sources.apply(db_session, "owner@example.com", NOW)
    db_session.commit()

    ntv = db_session.scalar(select(Source).where(Source.name == "NTV Telugu"))
    assert ntv.rights_status == "DISABLED" and ntv.active is False
    assert any(line.startswith("skip NTV Telugu") for line in log)
