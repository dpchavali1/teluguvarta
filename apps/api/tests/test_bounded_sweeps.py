"""Review 2026-09-29 #8: AI sweeps are bounded and checkpointed, job leases
are renewed and owned, and the worker recovers its session before
recording a failure."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from app.jobs import ai_retry, queue, worker
from app.jobs.generate import generate_stories
from app.jobs.queue import (
    MAX_JOB_ATTEMPTS,
    LeaseLost,
    claim_job,
    complete_job,
    enqueue_job,
    fail_job,
    renew_lease,
)
from app.models import Job, Source, SourceItem, Story, StorySource

from .conftest import requires_postgres
from .test_ai_retry import CountingProvider
from .test_generate import _classification, _generation


def _stories(db: Session, count: int) -> list[tuple[Story, SourceItem]]:
    source = Source(name="S", feed_url="https://example.org/feed.xml", rights_status="LINK_ONLY", active=True)
    db.add(source)
    db.flush()
    made = []
    for i in range(count):
        item = SourceItem(
            source_id=source.id, external_id=f"e{i}", url=f"https://example.org/{i}",
            title=f"Agency announces rule change {i}", published_at=datetime.now(UTC) - timedelta(hours=i),
            raw_hash=f"h{i}", ingest_status="CLUSTERED",
        )
        db.add(item)
        db.flush()
        story = Story(canonical_slug=f"s-{item.id}")
        db.add(story)
        db.flush()
        db.add(StorySource(story_id=story.id, source_item_id=item.id, role="PRIMARY", evidence_rank=1))
        made.append((story, item))
    db.commit()
    return made


def _responses(pairs):
    out = []
    for _story, item in pairs:
        out += [_classification(), _generation(item_id=item.id)]
    return out


@requires_postgres
def test_sweep_attempts_at_most_the_batch_newest_first(migrated_database, monkeypatch):
    monkeypatch.setenv("AI_SWEEP_BATCH_SIZE", "2")
    with Session(create_engine(migrated_database)) as db:
        made = _stories(db, 3)  # made[0] is newest
        provider = CountingProvider(_responses(made))
        monkeypatch.setattr("app.ai.gateway._resolve_provider", lambda name: provider)

        assert generate_stories(db) == 2
        for story, _ in made:
            db.refresh(story)
        assert [s.status for s, _ in made] == ["AI_READY", "AI_READY", "DRAFT"]

        assert generate_stories(db) == 1
        db.refresh(made[2][0])
        assert made[2][0].status == "AI_READY"


@requires_postgres
def test_sweep_starts_no_story_after_time_budget(migrated_database, monkeypatch):
    clock = iter([0.0, 0.0, ai_retry.SWEEP_TIME_BUDGET.total_seconds() + 1] + [999.0] * 10)
    monkeypatch.setattr(ai_retry, "monotonic", lambda: next(clock))
    with Session(create_engine(migrated_database)) as db:
        made = _stories(db, 3)
        provider = CountingProvider(_responses(made))
        monkeypatch.setattr("app.ai.gateway._resolve_provider", lambda name: provider)
        assert generate_stories(db) == 1


@requires_postgres
def test_finished_story_survives_a_crash_on_the_next(migrated_database, monkeypatch):
    with Session(create_engine(migrated_database)) as db:
        made = _stories(db, 2)
        provider = CountingProvider([_classification(), _generation(item_id=made[0][1].id), RuntimeError("boom")])
        monkeypatch.setattr("app.ai.gateway._resolve_provider", lambda name: provider)
        with pytest.raises(RuntimeError):
            generate_stories(db)
        db.rollback()
        db.refresh(made[0][0])
        assert made[0][0].status == "AI_READY"  # checkpointed before story 2 ran


@requires_postgres
def test_lost_lease_stops_the_handler_and_leaves_the_job_alone(migrated_database):
    with Session(create_engine(migrated_database)) as db:
        enqueue_job(db, "ai_classify", {}, dedupe_key="lease-1")
        db.commit()
        job = claim_job(db, ["ai_classify"])
        renew_lease(db, job)  # still ours

        # Another worker reclaims it after our lease "expired".
        db.execute(update(Job).where(Job.id == job.id).values(locked_at=datetime.now(UTC) + timedelta(seconds=1)))
        db.commit()
        with pytest.raises(LeaseLost):
            renew_lease(db, job)
        with pytest.raises(LeaseLost):
            complete_job(db, job)
        fail_job(db, job, "late failure")
        db.refresh(job)
        assert job.status == "RUNNING" and job.last_error is None


@requires_postgres
def test_expired_job_at_max_attempts_is_failed_not_reclaimed(migrated_database):
    with Session(create_engine(migrated_database)) as db:
        job = enqueue_job(db, "ai_classify", {}, dedupe_key="lease-2")
        job.status = "RUNNING"
        job.attempts = MAX_JOB_ATTEMPTS
        job.lock_expiry = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

        assert claim_job(db, ["ai_classify"]) is None
        db.refresh(job)
        assert job.status == "FAILED"
        assert job.attempts == MAX_JOB_ATTEMPTS


@requires_postgres
def test_worker_rolls_back_before_recording_a_failed_flush(migrated_database, monkeypatch):
    def broken_handler(db, job):
        db.add(Story(canonical_slug=None))  # NOT NULL violation at flush
        db.flush()

    monkeypatch.setattr(worker, "JOB_HANDLERS", {"ai_classify": broken_handler})
    with Session(create_engine(migrated_database)) as db:
        assert worker.process_one(db) is True
        job = db.scalars(select(Job).where(Job.type == "ai_classify")).one()
        assert job.status == "PENDING"
        assert "canonical_slug" in job.last_error
        assert queue.backoff_seconds(job.attempts) > 0
