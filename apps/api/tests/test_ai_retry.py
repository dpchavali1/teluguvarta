"""Review 2026-09-29 #1: AI retries are bounded per story across distinct
sweep windows, not only within one queue job. Time is advanced by patching
`ai_retry._now`, so each `generate_stories`/`translate_stories` call below
stands in for a separate time-bucketed sweep job."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.ai import gateway as gateway_module
from app.ai.providers.base import ProviderResponse, ProviderUnavailableError
from app.jobs import ai_retry
from app.jobs.generate import generate_stories
from app.jobs.translate import translate_stories
from app.models import AiWorkState, ReviewTask, StoryVariant

from .conftest import requires_postgres
from .test_generate import (
    _classification,
    _generation,
    _make_clustered_story,
    _make_source,
)
from .test_translate import _make_story_with_en_variant, _translation


class CountingProvider:
    name = "fake"

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[str] = []

    def complete(self, *, model, task, prompt, constrained=False):
        self.calls.append(task.value)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return ProviderResponse(output=item, tokens_in=100, tokens_out=50)


class Clock:
    def __init__(self, monkeypatch):
        self.now = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
        monkeypatch.setattr(ai_retry, "_now", lambda: self.now)

    def advance(self, delta: timedelta) -> None:
        self.now += delta


def _provider(monkeypatch, responses) -> CountingProvider:
    provider = CountingProvider(responses)
    monkeypatch.setattr(gateway_module, "_resolve_provider", lambda name: provider)
    return provider


def _state(db, story_id, stage) -> AiWorkState | None:
    return db.scalars(select(AiWorkState).where(AiWorkState.story_id == story_id, AiWorkState.stage == stage)).first()


@requires_postgres
def test_unavailable_provider_backs_off_across_sweeps(migrated_database, monkeypatch):
    clock = Clock(monkeypatch)
    with Session(create_engine(migrated_database)) as db:
        story, item = _make_clustered_story(db, _make_source(db))
        provider = _provider(
            monkeypatch,
            [ProviderUnavailableError("down"), _classification(), _generation(item_id=item.id)],
        )

        generate_stories(db)
        assert provider.calls == ["relevance_categorization"]

        # The next sweep window is inside the backoff: no provider call.
        clock.advance(timedelta(minutes=1))
        generate_stories(db)
        assert len(provider.calls) == 1

        clock.advance(timedelta(minutes=2))
        generate_stories(db)
        assert provider.calls == ["relevance_categorization", "relevance_categorization", "summary"]
        db.refresh(story)
        assert story.status == "AI_READY"
        assert _state(db, story.id, ai_retry.STAGE_GENERATE) is None  # cleared on success


@requires_postgres
def test_successful_classification_is_not_repaid_when_summary_fails(migrated_database, monkeypatch):
    clock = Clock(monkeypatch)
    with Session(create_engine(migrated_database)) as db:
        story, item = _make_clustered_story(db, _make_source(db))
        provider = _provider(
            monkeypatch,
            [_classification(), ProviderUnavailableError("down"), _generation(item_id=item.id)],
        )

        generate_stories(db)
        state = _state(db, story.id, ai_retry.STAGE_GENERATE)
        assert state is not None and state.cached_classification is not None

        clock.advance(timedelta(minutes=5))
        generate_stories(db)
        assert provider.calls == ["relevance_categorization", "summary", "summary"]
        db.refresh(story)
        assert story.status == "AI_READY"


@requires_postgres
def test_invalid_output_exhausts_to_editorial_hold(migrated_database, monkeypatch):
    clock = Clock(monkeypatch)
    with Session(create_engine(migrated_database)) as db:
        story, item = _make_clustered_story(db, _make_source(db))
        invalid = {"not": "a generation result"}
        # Each attempt: classify is cached after the first, then the summary
        # call fails schema validation twice (gateway's constrained retry).
        provider = _provider(monkeypatch, [_classification()] + [invalid] * 2 * ai_retry.MAX_INVALID_ATTEMPTS)

        for _ in range(ai_retry.MAX_INVALID_ATTEMPTS):
            generate_stories(db)
            clock.advance(timedelta(hours=1))

        db.refresh(story)
        db.refresh(item)
        assert story.status == "REVIEW_REQUIRED"
        assert item.ingest_status == "REVIEW"
        task = db.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).one()
        assert "AI_RETRIES_EXHAUSTED" in task.reason
        assert _state(db, story.id, ai_retry.STAGE_GENERATE).failure_class == "EXHAUSTED"

        calls_before = len(provider.calls)
        clock.advance(timedelta(days=1))
        assert generate_stories(db) == 0
        assert len(provider.calls) == calls_before


@requires_postgres
def test_transient_failures_are_bounded(migrated_database, monkeypatch):
    clock = Clock(monkeypatch)
    with Session(create_engine(migrated_database)) as db:
        story, _item = _make_clustered_story(db, _make_source(db))
        provider = _provider(monkeypatch, [ProviderUnavailableError("down")] * ai_retry.MAX_TRANSIENT_FAILURES)

        for _ in range(ai_retry.MAX_TRANSIENT_FAILURES):
            generate_stories(db)
            clock.advance(ai_retry.BACKOFF_MAX)

        assert len(provider.calls) == ai_retry.MAX_TRANSIENT_FAILURES
        db.refresh(story)
        assert story.status == "REVIEW_REQUIRED"
        generate_stories(db)
        assert len(provider.calls) == ai_retry.MAX_TRANSIENT_FAILURES


def test_backoff_is_exponential_and_capped():
    now = datetime(2026, 9, 29, tzinfo=UTC)
    delays = []
    state = AiWorkState(story_id=None, stage="GENERATE", input_version="v", invalid_attempts=0, transient_failures=0)

    class _Db:
        def add(self, _): ...
        def flush(self): ...

    for _ in range(12):
        ai_retry.record_failure(
            _Db(), state, story_id=None, stage="GENERATE", version="v",
            status=gateway_module.GatewayStatus.DEFERRED, now=now,
        )
        delays.append(state.next_attempt_at - now)
    assert delays[0] == timedelta(minutes=2)
    assert delays[1] == timedelta(minutes=4)
    assert max(delays) == ai_retry.BACKOFF_MAX


@requires_postgres
def test_translation_backs_off_and_resets_on_corrected_english(migrated_database, monkeypatch):
    Clock(monkeypatch)
    monkeypatch.setenv("AI_TRANSLATION_ENABLED", "1")
    with Session(create_engine(migrated_database)) as db:
        story, en = _make_story_with_en_variant(db)
        provider = _provider(monkeypatch, [ProviderUnavailableError("down"), _translation()])

        translate_stories(db)
        translate_stories(db)  # same window: backing off
        assert len(provider.calls) == 1

        # A correction changes the English input: new work, retried at once.
        en.why_matters = "Applicants should expect longer waits this year."
        db.commit()
        translate_stories(db)
        assert len(provider.calls) == 2
        assert db.scalars(
            select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "te")
        ).first() is not None
        assert _state(db, story.id, ai_retry.STAGE_TRANSLATE) is None
