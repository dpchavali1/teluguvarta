"""T13: derives the Telugu `StoryVariant` from the already-approved English
one via the T10 AI gateway's `TRANSLATION_EN_TE` task, then validates the
result before trusting it (§4.3) — a story never serves a broken or
silently-truncated Telugu translation; a failed-QA or missing variant falls
back to English instead (`app/content/variants.py`, wired at read time by
whichever caller renders the story).

One job type, `ai_translate` (reserved in T03's `ck_jobs_type` list),
mirroring T09/T11's "one handler per pipeline slice" precedent: generate,
glossary-correct, QA, and (for a sampled subset of sensitive categories)
route into the review queue — all in one gateway round-trip's worth of
work, since none of these steps has independent retry value of its own.

Runs for *every* story with an `en` variant and no `te` variant yet,
regardless of `Story.status` — English is canonical and always exists
first (T11), but a Telugu reader shouldn't wait for a story to reach
`PUBLISHED` before translation starts. This is also what makes T12's
correction hook ("delete the `te` variant to invalidate it") actually
result in regeneration: the next sweep picks the story back up exactly
because it once again has no `te` variant.
"""

from __future__ import annotations

import os
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.ai import AiGateway, GatewayStatus, Task
from app.ai.contracts import TranslationResult
from app.content.glossary import apply_glossary
from app.content.qa import find_qa_issues
from app.jobs.queue import enqueue_job
from app.models import Job, ReviewTask, Story, StoryVariant

TRANSLATE_INTERVAL_MINUTES = 2

# §4.3: during the early-launch phase, sample a percentage of political/
# legal/financial Telugu translations into the review queue even when QA
# passes — these categories carry more risk from a subtle mistranslation
# than a generic story does.
SAMPLED_SENSITIVITIES = frozenset({"IMMIGRATION", "LEGAL", "FINANCIAL"})
SAMPLE_RATE_ENV_VAR = "TELUGU_REVIEW_SAMPLE_RATE"
DEFAULT_SAMPLE_RATE = 0.2


def _now() -> datetime:
    return datetime.now(UTC)


def _sample_rate() -> float:
    raw = os.environ.get(SAMPLE_RATE_ENV_VAR)
    if raw is None:
        return DEFAULT_SAMPLE_RATE
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_SAMPLE_RATE


def _translate_prompt(en: StoryVariant) -> str:
    return (
        "Translate this English news story into Telugu. Preserve every "
        "number, date, currency amount, URL, and negation exactly — never "
        "omit or approximate one. Use the standard Telugu spelling for any "
        "proper noun with a well-known one.\n"
        f'headline="{en.headline}"\n'
        f'summary="{en.summary}"\n'
        f'why_matters="{en.why_matters or ""}"'
    )


def _translate_story(db: Session, story: Story, en: StoryVariant) -> None:
    gateway = AiGateway(db)
    outcome = gateway.run_task(
        Task.TRANSLATION_EN_TE, _translate_prompt(en), story_id=story.id, result_model=TranslationResult
    )
    if outcome.status in (GatewayStatus.HOLD, GatewayStatus.UNAVAILABLE, GatewayStatus.CLASSIFICATION_ONLY):
        return  # retried next sweep — no `te` variant created, per §7.5
    result = outcome.result
    if not isinstance(result, TranslationResult):
        return  # OK carries a result_model-typed instance whenever status is OK

    headline_te = apply_glossary(en.headline, result.headline_te)
    summary_te = apply_glossary(en.summary, result.summary_te)
    why_matters_te = (
        apply_glossary(en.why_matters, result.why_matters_te)
        if en.why_matters and result.why_matters_te
        else result.why_matters_te
    )

    issues = find_qa_issues(en.headline, headline_te) + find_qa_issues(en.summary, summary_te)
    if en.why_matters and why_matters_te:
        issues += find_qa_issues(en.why_matters, why_matters_te)
    qa_status = "FAILED" if issues else "PASSED"

    db.add(
        StoryVariant(
            story_id=story.id,
            language="te",
            headline=headline_te,
            summary=summary_te,
            why_matters=why_matters_te,
            model_version=Task.TRANSLATION_EN_TE.value,
            qa_status=qa_status,
        )
    )

    if qa_status == "PASSED" and story.sensitivity in SAMPLED_SENSITIVITIES and random.random() < _sample_rate():
        db.add(ReviewTask(story_id=story.id, reason="TELUGU_TRANSLATION_SAMPLE_REVIEW", status="PENDING"))

    db.flush()


def translate_stories(db: Session) -> int:
    """Every `Story` with an `en` variant and no `te` variant yet — created
    fresh by T11's generation step, or re-created after T12's correction
    hook deletes a stale `te` variant. Idempotent: a story only leaves this
    set once a `te` variant row actually exists."""
    en_variants = aliased(StoryVariant)
    te_variants = aliased(StoryVariant)
    rows = db.execute(
        select(Story, en_variants)
        .join(en_variants, (en_variants.story_id == Story.id) & (en_variants.language == "en"))
        .outerjoin(te_variants, (te_variants.story_id == Story.id) & (te_variants.language == "te"))
        .where(te_variants.id.is_(None))
    ).all()

    for story, en in rows:
        _translate_story(db, story, en)

    db.commit()
    return len(rows)


def run_ai_translate(db: Session, job: Job) -> None:
    """Job handler wrapping `translate_stories` for the worker."""
    translate_stories(db)


def _translate_window(now: datetime) -> datetime:
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    elapsed_minutes = int((now - epoch).total_seconds() // 60)
    bucket_start_minutes = (elapsed_minutes // TRANSLATE_INTERVAL_MINUTES) * TRANSLATE_INTERVAL_MINUTES
    return epoch + timedelta(minutes=bucket_start_minutes)


def schedule_ai_translate(db: Session) -> Job | None:
    """Enqueues one `ai_translate` job per `TRANSLATE_INTERVAL_MINUTES`
    window, same time-bucketed-dedupe_key pattern as `schedule_ai_classify`."""
    now = _now()
    dedupe_key = f"ai_translate:{_translate_window(now).isoformat()}"
    return enqueue_job(db, "ai_translate", {}, dedupe_key=dedupe_key)
