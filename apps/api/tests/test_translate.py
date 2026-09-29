"""T13 acceptance tests: English->Telugu variant generation via the AI
gateway, glossary enforcement, automated QA, English-fallback selection, and
the correction-invalidation -> re-translation loop. `FakeProvider` pattern
matches `test_ai_gateway.py`/`test_generate.py` — these tests care about
T13's routing/QA/fallback logic, not real model output.
"""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.ai import gateway as gateway_module
from app.ai.providers.base import ProviderResponse
from app.content.glossary import apply_glossary
from app.content.qa import find_qa_issues
from app.content.variants import resolve_display_variant
from app.jobs import translate as translate_module
from app.jobs.translate import (
    run_ai_translate,
    schedule_ai_translate,
    translate_stories,
)
from app.models import Job, ReviewTask, Story, StoryVariant
from app.schemas import StoryVariantOut

from .conftest import requires_postgres


class FakeProvider:
    name = "fake"

    def __init__(self, responses):
        self._responses = list(responses)

    def complete(self, *, model, task, prompt, constrained=False):
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return ProviderResponse(output=item, tokens_in=100, tokens_out=50)


def _use_fake_provider(monkeypatch, responses):
    provider = FakeProvider(responses)
    monkeypatch.setattr(gateway_module, "_resolve_provider", lambda name: provider)
    return provider


def _translation(**overrides):
    base = {
        "headline_te": "USCIS కొత్త నిబంధనలు ప్రకటించింది",
        "summary_te": "మార్చి 5, 2026న USCIS వీసా ప్రాసెసింగ్ సమయాలను మార్చింది. https://uscis.gov/notice.",
        "why_matters_te": "దరఖాస్తుదారులు ఎక్కువ కాలం వేచి ఉండాలి.",
    }
    base.update(overrides)
    return base


def _make_story_with_en_variant(db: Session, **variant_overrides) -> tuple[Story, StoryVariant]:
    story = Story(canonical_slug="story-en-1")
    db.add(story)
    db.flush()
    variant = StoryVariant(
        story_id=story.id,
        language="en",
        headline="USCIS announces new rule",
        summary="On March 5, 2026, USCIS changed visa processing times. See https://uscis.gov/notice.",
        why_matters="Applicants should expect longer waits.",
        model_version="summary",
        qa_status="PENDING",
    )
    for key, value in variant_overrides.items():
        setattr(variant, key, value)
    db.add(variant)
    db.commit()
    return story, variant


@requires_postgres
def test_translation_passes_qa_and_applies_glossary(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        story, _en = _make_story_with_en_variant(db)
        # Model output leaves "USCIS" in Latin script and drops nothing —
        # the naive rendering `apply_glossary` must correct.
        _use_fake_provider(
            monkeypatch,
            [
                _translation(
                    headline_te="USCIS కొత్త నిబంధనలు ప్రకటించింది",
                    summary_te=(
                        "మార్చి 5, 2026న USCIS వీసా ప్రాసెసింగ్ సమయాలను మార్చింది. "
                        "https://uscis.gov/notice."
                    ),
                )
            ],
        )

        processed = translate_stories(db)
        assert processed == 1

        te = db.scalars(
            select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "te")
        ).first()
        assert te is not None
        assert te.qa_status == "PASSED"
        assert "యుఎస్‌సిఐఎస్" in te.headline  # canonical glossary spelling, not the raw "USCIS"
        assert "USCIS" not in te.headline


@requires_postgres
def test_qa_failure_drops_number_date_and_url(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        story, _en = _make_story_with_en_variant(db)
        # Translation drops the date, the URL, and mangles the number.
        _use_fake_provider(
            monkeypatch,
            [_translation(summary_te="USCIS వీసా ప్రాసెసింగ్ సమయాలను మార్చింది.")],
        )

        translate_stories(db)

        te = db.scalars(
            select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "te")
        ).first()
        assert te is not None
        assert te.qa_status == "FAILED"


@requires_postgres
def test_translate_is_idempotent_and_reruns_after_invalidation(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        story, _en = _make_story_with_en_variant(db)
        _use_fake_provider(monkeypatch, [_translation()])

        assert translate_stories(db) == 1
        # Second sweep: a `te` variant already exists, so no gateway call is
        # queued — only one response was ever provided above, so a second
        # real call would raise IndexError.
        assert translate_stories(db) == 0

        te = db.scalars(
            select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "te")
        ).first()
        db.delete(te)  # simulates T12's correction-invalidation hook
        db.commit()

        _use_fake_provider(monkeypatch, [_translation()])
        assert translate_stories(db) == 1


@requires_postgres
def test_sensitive_category_samples_into_review_queue(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        story, _en = _make_story_with_en_variant(db)
        story.sensitivity = "IMMIGRATION"
        db.commit()
        monkeypatch.setenv("TELUGU_REVIEW_SAMPLE_RATE", "1")
        _use_fake_provider(monkeypatch, [_translation()])

        translate_stories(db)

        review = db.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).first()
        assert review is not None
        assert review.reason == "TELUGU_TRANSLATION_SAMPLE_REVIEW"


def test_glossary_forces_canonical_spelling_over_naive_translation():
    en = "The White House issued a statement about USCIS."
    naive = "White House USCIS గురించి ఒక ప్రకటన చేసింది."
    corrected = apply_glossary(en, naive)
    assert "వైట్ హౌస్" in corrected
    assert "యుఎస్‌సిఐఎస్" in corrected
    assert "White House" not in corrected
    assert "USCIS" not in corrected


def test_qa_catches_dropped_number_date_and_url():
    en = "On March 5, 2026, 40,000 visas were processed. See https://example.gov/notice."
    te_missing_everything = "వీసాలు ప్రాసెస్ చేయబడ్డాయి."
    issues = find_qa_issues(en, te_missing_everything)
    assert any(issue.startswith("MISSING_NUMBER") for issue in issues)
    assert any(issue.startswith("MISSING_DATE") for issue in issues)
    assert any(issue.startswith("MISSING_URL") for issue in issues)


def test_qa_passes_when_number_date_and_url_survive():
    en = "On March 5, 2026, 40,000 visas were processed. See https://example.gov/notice."
    te = "మార్చి 5, 2026న 40,000 వీసాలు ప్రాసెస్ చేయబడ్డాయి. https://example.gov/notice."
    assert find_qa_issues(en, te) == []


def test_resolve_display_variant_falls_back_to_english_when_te_missing():
    en = StoryVariantOut(language="en", headline="EN headline", summary="EN summary")
    resolved = resolve_display_variant({"en": en}, "te")
    assert resolved is not None
    assert resolved.served_language == "en"
    assert resolved.fallback is True


def test_resolve_display_variant_falls_back_to_english_when_te_failed_qa():
    en = StoryVariantOut(language="en", headline="EN headline", summary="EN summary")
    te = StoryVariantOut(language="te", headline="TE headline", summary="TE summary", qa_status="FAILED")
    resolved = resolve_display_variant({"en": en, "te": te}, "te")
    assert resolved is not None
    assert resolved.served_language == "en"
    assert resolved.fallback is True


def test_resolve_display_variant_serves_te_when_passed_qa():
    en = StoryVariantOut(language="en", headline="EN headline", summary="EN summary")
    te = StoryVariantOut(language="te", headline="TE headline", summary="TE summary", qa_status="PASSED")
    resolved = resolve_display_variant({"en": en, "te": te}, "te")
    assert resolved is not None
    assert resolved.served_language == "te"
    assert resolved.fallback is False


@requires_postgres
def test_translation_flag_off_schedules_and_runs_nothing(migrated_database, monkeypatch):
    monkeypatch.setenv("AI_TRANSLATION_ENABLED", "false")
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        _make_story_with_en_variant(db)
        assert schedule_ai_translate(db) is None
        assert db.scalars(select(Job).where(Job.type == "ai_translate")).first() is None

        # A job queued before the flag was turned off must not translate.
        called = []
        monkeypatch.setattr(translate_module, "translate_stories", lambda _db: called.append(1))
        run_ai_translate(db, Job(type="ai_translate", payload={}))
        assert called == []


@requires_postgres
def test_translation_flag_on_schedules_and_runs(migrated_database, monkeypatch):
    monkeypatch.setenv("AI_TRANSLATION_ENABLED", "true")
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        assert schedule_ai_translate(db) is not None

        called = []
        monkeypatch.setattr(translate_module, "translate_stories", lambda _db: called.append(1))
        run_ai_translate(db, Job(type="ai_translate", payload={}))
        assert called == [1]
