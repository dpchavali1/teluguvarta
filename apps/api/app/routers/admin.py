"""Admin endpoints. Auth is real as of T05 — see app/auth.py.

Editorial workflow (T12): approve/reject/retract/correct enforce T03's
DB-backed `stories.status` state machine (extended by the
`73a24fe47a9f` migration with the reject-only ARCHIVED transitions) and
write an `AuditEvent` for every mutation, no exceptions. The actual
auto-publish sweep that these kill switches gate lives in
`app/jobs/publish.py` (the `publish_scheduler` job) — this router only
exposes the read-only kill-switch view and the human-editor actions.

Source registry (docs/tickets/T06.md): only `DISABLED` and `LINK_ONLY` are
reachable rights tiers in this build phase (ADR-002); moving a source off
`DISABLED` requires rights evidence to already be on file and is restricted
to the `ADMIN` role (see the ADR-002 addendum) — an `EDITOR` can create/edit
everything else about a source but cannot flip the rights gate itself.
"""

import hashlib
import os
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.adapters.feed_probe import probe_feed
from app.admin_lists import audit_history, review_queue, story_library
from app.ai.budget import (
    budget_mode,
    cost_by_task_and_day,
    is_over_monthly_budget,
    month_to_date_cost_usd,
    reporting_windows,
    today_cost_usd,
)
from app.ai.cost_report import MAX_RANGE_DAYS, cost_report
from app.auth import AdminPrincipal, current_admin
from app.content.geography import (
    event_countries_many,
    normalize_countries,
    normalize_country,
    set_event_countries,
)
from app.content.importance import recompute_importance
from app.content.publication import (
    HEADLINE_COPIES_SOURCE,
    MIN_SUMMARY_SENTENCES,
    MIN_SUMMARY_WORDS,
    SUMMARY_REPEATS_HEADLINE,
    SUMMARY_TOO_SHORT,
    validate_for_publication,
)
from app.content.qa import find_variant_qa_issues
from app.content.rights import unpermitted_sources
from app.content.variants import EDITOR_MODEL_VERSION
from app.coverage_report import coverage_report
from app.db import get_db
from app.errors import APIError
from app.jobs import ai_retry
from app.jobs.brief_lane import BRIEF_ACTOR, briefs_enabled, daily_cap, published_today
from app.jobs.source_fetch import CIRCUIT_BREAKER_THRESHOLD
from app.jobs.translate import TRANSLATABLE_STATUSES
from app.models import (
    AiWorkState,
    AuditEvent,
    Correction,
    Job,
    ReaderReport,
    ReviewTask,
    Source,
    SourceItem,
    Story,
    StorySource,
    StoryTopic,
    StoryVariant,
    StoryWhyMattersCache,
    Topic,
    User,
    XAccount,
)
from app.ops_status import ops_statuses
from app.pipeline_status import pipeline_status
from app.rate_limit import rate_limit_admin
from app.reader_reports import ResolveError, resolve_report
from app.schemas import (
    AdminActionRequest,
    AdminActionResponse,
    AdminAiHoldOut,
    AdminAuditPageOut,
    AdminAutoBriefOut,
    AdminCorrectionOut,
    AdminCorrectionRequest,
    AdminCountriesRequest,
    AdminDraftRequest,
    AdminFeedTestOut,
    AdminFeedTestRequest,
    AdminImportanceRequest,
    AdminJobOut,
    AdminReaderReportListOut,
    AdminReaderReportOut,
    AdminReaderReportResolveRequest,
    AdminRejectRequest,
    AdminRetryAiRequest,
    AdminSourceCreate,
    AdminSourceOut,
    AdminSourceUpdate,
    AdminStoryDetailOut,
    AdminStoryListOut,
    AdminStorySourceOut,
    AdminTeluguRepairOut,
    AdminTeluguRepairRequest,
    AdminTopicsRequest,
    AdminXAccountCreate,
    AdminXAccountOut,
    AdminXAccountUpdate,
    AiCostReportOut,
    AiCostRowOut,
    AiCostSummaryOut,
    CoverageReportOut,
    JobQueueHealthOut,
    KillSwitchesOut,
    Language,
    ObservabilityOut,
    OpsCheckOut,
    PipelineStatusOut,
    ReaderReportCategory,
    ReaderReportStatus,
    ReviewQueueItemOut,
    ReviewQueuePageOut,
    RightsEvidence,
    RuntimeSwitchOut,
    RuntimeSwitchUpdate,
    SourceIngestionHealthOut,
    StoryFormat,
    StoryStatus,
    StoryVariantOut,
    TeluguFilter,
    XCostSummaryOut,
)
from app.switches import SWITCH_KEYS, SwitchKey, env_allows, set_switch, switch_row
from app.x.budget import (
    is_low_priority,
    month_to_date_cost_usd_for_account,
    recent_error_count,
)
from app.x.budget import is_over_monthly_budget as x_is_over_monthly_budget
from app.x.budget import month_to_date_cost_usd as x_month_to_date_cost_usd

router = APIRouter(
    prefix="/v1/admin", tags=["admin"], dependencies=[Depends(current_admin), Depends(rate_limit_admin)]
)

# ADR-002: only these two tiers are reachable in this build phase.
ENABLABLE_RIGHTS_STATUSES = {"DISABLED", "LINK_ONLY"}
# Fields that must already be on file before a source can move off DISABLED.
REQUIRED_EVIDENCE_FIELDS = ("rights_evidence_url", "rights_reviewed_at", "reviewer")


def _write_audit_event(db: Session, actor: str, action: str, entity_type: str, entity_id: UUID, metadata: dict) -> None:
    db.add(AuditEvent(actor=actor, action=action, entity_type=entity_type, entity_id=entity_id, metadata_=metadata))


def _enforce_enable_gate(admin: AdminPrincipal, new_status: str, evidence: dict[str, Any]) -> None:
    """ADR-002 gate for moving a source off DISABLED — shared by create and
    update so there is exactly one implementation. `evidence` maps each of
    REQUIRED_EVIDENCE_FIELDS to its would-be value after the write."""
    if new_status not in ENABLABLE_RIGHTS_STATUSES:
        raise APIError(
            422,
            "RIGHTS_TIER_NOT_ENABLED",
            f"'{new_status}' is not enabled in this build phase — only DISABLED and LINK_ONLY "
            "are reachable per ADR-002",
        )
    if new_status == "DISABLED":
        return
    if admin.role != "ADMIN":
        raise APIError(403, "FORBIDDEN", "Only an ADMIN can enable a source (move it off DISABLED)")
    missing = [field for field in REQUIRED_EVIDENCE_FIELDS if not evidence.get(field)]
    if missing:
        raise APIError(
            422,
            "RIGHTS_EVIDENCE_REQUIRED",
            f"Cannot enable source: missing rights evidence field(s) {', '.join(missing)}",
        )


def _enforce_description_evidence_gate(admin: AdminPrincipal, source: Source, *, turning_on: bool) -> None:
    """ADR-020: storing a feed description needs an ADMIN, a LINK_ONLY source
    and a recorded public-domain basis. A source that stops meeting that while
    flagged (e.g. moved to DISABLED) has the flag cleared."""
    allowed = source.rights_status == "LINK_ONLY" and bool((source.rights_evidence or {}).get("public_domain_basis"))
    if turning_on:
        if admin.role != "ADMIN":
            raise APIError(403, "FORBIDDEN", "Only an ADMIN can turn on description evidence")
        if not allowed:
            raise APIError(
                422,
                "DESCRIPTION_EVIDENCE_NOT_ALLOWED",
                "Description evidence needs a LINK_ONLY source and rights_evidence.public_domain_basis (ADR-020)",
            )
    elif source.description_evidence and not allowed:
        source.description_evidence = False


def _source_out(source: Source) -> AdminSourceOut:
    return AdminSourceOut(
        id=source.id,
        name=source.name,
        base_url=source.base_url,
        feed_url=source.feed_url,
        source_type=source.source_type,
        country=source.country,
        language=source.language,
        rights_status=source.rights_status,
        rights_evidence_url=source.rights_evidence_url,
        rights_reviewed_at=source.rights_reviewed_at,
        reviewer=source.reviewer,
        rights_evidence=RightsEvidence(**source.rights_evidence),
        description_evidence=source.description_evidence,
        refresh_minutes=source.refresh_minutes,
        category=source.category,
        active=source.active,
        fail_count=source.fail_count,
        last_success_at=source.last_success_at,
        last_error_at=source.last_error_at,
    )


@router.get("/sources")
def list_sources(db: Session = Depends(get_db)) -> list[AdminSourceOut]:
    sources = db.scalars(select(Source).order_by(Source.name)).all()
    return [_source_out(s) for s in sources]


@router.post("/sources/test-feed")
def test_feed(body: AdminFeedTestRequest) -> AdminFeedTestOut:
    """Preview a candidate feed URL (read-only; nothing is saved)."""
    result = probe_feed(body.feed_url.strip())
    return AdminFeedTestOut(
        ok=result.ok, item_count=result.item_count, headlines=result.headlines, error=result.error
    )


@router.post("/sources", status_code=201)
def create_source(
    body: AdminSourceCreate, admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)
) -> AdminSourceOut:
    """Create a source. With no rights fields it starts DISABLED/inactive. A
    preset flow may also pass rights fields to enable + activate in one call;
    that goes through the same ADR-002 gate as PATCH (ADMIN only, evidence URL
    and reviewer required) — a human still supplies the evidence."""
    enabling = body.rights_status is not None and body.rights_status != "DISABLED"
    if body.active and not enabling:
        raise APIError(422, "SOURCE_NOT_ENABLED", "A source cannot be activated while its rights are DISABLED")
    reviewed_at = body.rights_reviewed_at or (datetime.now(UTC) if enabling else None)
    if body.rights_status is not None:
        _enforce_enable_gate(
            admin,
            body.rights_status,
            {
                "rights_evidence_url": body.rights_evidence_url,
                "rights_reviewed_at": reviewed_at,
                "reviewer": body.reviewer,
            },
        )

    source = Source(
        name=body.name,
        base_url=body.base_url,
        feed_url=body.feed_url,
        source_type=body.source_type,
        country=body.country,
        language=body.language,
        refresh_minutes=body.refresh_minutes,
        category=body.category,
    )
    if enabling:
        source.rights_status = body.rights_status
        source.rights_evidence_url = body.rights_evidence_url
        source.rights_reviewed_at = reviewed_at
        source.reviewer = body.reviewer
        if body.rights_evidence is not None:
            source.rights_evidence = body.rights_evidence.model_dump(mode="json")
        source.active = bool(body.active)
    db.add(source)
    db.flush()
    audit = {"name": source.name}
    if enabling:
        audit.update(rights_status=source.rights_status, active=source.active, reviewer=source.reviewer)
    _write_audit_event(db, admin.email, "SOURCE_CREATED", "source", source.id, audit)
    db.commit()
    db.refresh(source)
    return _source_out(source)


@router.patch("/sources/{source_id}")
def update_source(
    source_id: UUID,
    body: AdminSourceUpdate,
    admin: AdminPrincipal = Depends(current_admin),
    db: Session = Depends(get_db),
) -> AdminSourceOut:
    source = db.get(Source, source_id)
    if source is None:
        raise APIError(404, "SOURCE_NOT_FOUND", f"No source with id '{source_id}'")

    updates = body.model_dump(exclude_unset=True, exclude={"rights_evidence"})
    # Dumped separately (with mode="json") so nested datetimes serialize to
    # strings for the JSONB column — `updates` above keeps real datetime
    # objects, since those map onto real DateTime columns.
    rights_evidence = body.rights_evidence.model_dump(mode="json") if body.rights_evidence is not None else None
    new_rights_status = updates.get("rights_status")

    if new_rights_status is not None and new_rights_status not in ENABLABLE_RIGHTS_STATUSES:
        _enforce_enable_gate(admin, new_rights_status, {})
    if new_rights_status is not None and new_rights_status != "DISABLED" and new_rights_status != source.rights_status:
        merged: dict[str, Any] = {field: updates.get(field, getattr(source, field)) for field in REQUIRED_EVIDENCE_FIELDS}
        _enforce_enable_gate(admin, new_rights_status, merged)

    was_describing = source.description_evidence
    for field, value in updates.items():
        setattr(source, field, value)
    if rights_evidence is not None:
        source.rights_evidence = rights_evidence
    _enforce_description_evidence_gate(
        admin, source, turning_on=updates.get("description_evidence") is True and not was_describing
    )
    if not source.description_evidence:
        # ADR-020: turning the flag off (or leaving LINK_ONLY) drops stored text.
        db.execute(update(SourceItem).where(SourceItem.source_id == source.id).values(description=None))

    audit_metadata = body.model_dump(exclude_unset=True, mode="json")
    _write_audit_event(db, admin.email, "SOURCE_UPDATED", "source", source.id, audit_metadata)
    db.commit()
    db.refresh(source)
    return _source_out(source)


def _x_account_out(db: Session, account: XAccount, source: Source) -> AdminXAccountOut:
    now = datetime.now(UTC)
    over_budget = x_is_over_monthly_budget(db, now)
    return AdminXAccountOut(
        id=account.id,
        source_id=account.source_id,
        x_user_id=account.x_user_id,
        handle=account.handle,
        priority=account.priority,
        polling_cadence=account.polling_cadence,
        since_id=account.since_id,
        budget_class=account.budget_class,
        rights_status=source.rights_status,
        active=source.active,
        last_success_at=source.last_success_at,
        last_error_at=source.last_error_at,
        fail_count=source.fail_count,
        circuit_breaker_tripped=source.fail_count >= CIRCUIT_BREAKER_THRESHOLD,
        recent_error_count_24h=recent_error_count(db, account.id, now - timedelta(hours=24)),
        month_to_date_cost_usd=month_to_date_cost_usd_for_account(db, account.id, now),
        budget_paused=over_budget and is_low_priority(account),
    )


@router.get("/x-accounts")
def list_x_accounts(db: Session = Depends(get_db)) -> list[AdminXAccountOut]:
    rows = db.execute(select(XAccount, Source).join(Source, XAccount.source_id == Source.id)).all()
    return [_x_account_out(db, account, source) for account, source in rows]


@router.post("/sources/{source_id}/x-account", status_code=201)
def create_x_account(
    source_id: UUID,
    body: AdminXAccountCreate,
    admin: AdminPrincipal = Depends(current_admin),
    db: Session = Depends(get_db),
) -> AdminXAccountOut:
    source = db.get(Source, source_id)
    if source is None:
        raise APIError(404, "SOURCE_NOT_FOUND", f"No source with id '{source_id}'")
    if db.scalar(select(XAccount).where(XAccount.source_id == source_id)) is not None:
        raise APIError(409, "X_ACCOUNT_ALREADY_LINKED", f"Source '{source_id}' already has an X account linked")
    if db.scalar(select(XAccount).where(XAccount.x_user_id == body.x_user_id)) is not None:
        raise APIError(409, "X_USER_ID_ALREADY_LINKED", f"X user id '{body.x_user_id}' is already linked to a source")

    account = XAccount(
        source_id=source_id,
        x_user_id=body.x_user_id,
        handle=body.handle,
        priority=body.priority,
        polling_cadence=body.polling_cadence,
        budget_class=body.budget_class,
    )
    db.add(account)
    db.flush()
    _write_audit_event(
        db, admin.email, "X_ACCOUNT_CREATED", "x_account", account.id,
        {"source_id": str(source_id), "x_user_id": account.x_user_id, "handle": account.handle},
    )
    db.commit()
    db.refresh(account)
    return _x_account_out(db, account, source)


@router.patch("/sources/{source_id}/x-account")
def update_x_account(
    source_id: UUID,
    body: AdminXAccountUpdate,
    admin: AdminPrincipal = Depends(current_admin),
    db: Session = Depends(get_db),
) -> AdminXAccountOut:
    source = db.get(Source, source_id)
    if source is None:
        raise APIError(404, "SOURCE_NOT_FOUND", f"No source with id '{source_id}'")
    account = db.scalar(select(XAccount).where(XAccount.source_id == source_id))
    if account is None:
        raise APIError(404, "X_ACCOUNT_NOT_FOUND", f"Source '{source_id}' has no linked X account")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(account, field, value)

    _write_audit_event(db, admin.email, "X_ACCOUNT_UPDATED", "x_account", account.id, updates)
    db.commit()
    db.refresh(account)
    return _x_account_out(db, account, source)


@router.get("/kill-switches")
def get_kill_switches(db: Session = Depends(get_db)) -> KillSwitchesOut:
    return KillSwitchesOut(
        auto_publish_global=os.environ.get("AUTO_PUBLISH_GLOBAL", "false").lower() == "true",
        auto_publish_category_immigration=os.environ.get("AUTO_PUBLISH_CATEGORY_IMMIGRATION", "false").lower()
        == "true",
        auto_publish_briefs=briefs_enabled(),
        auto_publish_briefs_daily_cap=daily_cap(),
        briefs_published_today=published_today(db, datetime.now(UTC)),
    )


# ADR-031: dashboard pause switches. Stories waiting on each: new stories sit
# in DRAFT while AI is paused, finished ones in AI_READY while auto-publish is.
_SWITCH_WAITING_STATUS = {"ai": "DRAFT", "auto_publish": "AI_READY"}


def _switch_out(db: Session, key: SwitchKey) -> RuntimeSwitchOut:
    row = switch_row(db, key)
    enabled = True if row is None else row.enabled
    allowed = env_allows(key)
    waiting = db.scalar(select(func.count(Story.id)).where(Story.status == _SWITCH_WAITING_STATUS[key])) or 0
    return RuntimeSwitchOut(
        key=key, enabled=enabled, env_allows=allowed, effective=enabled and allowed,
        updated_by=row.updated_by if row else None, updated_at=row.updated_at if row else None,
        note=row.note if row else None, waiting=waiting,
    )


@router.get("/switches")
def list_switches(db: Session = Depends(get_db)) -> list[RuntimeSwitchOut]:
    return [_switch_out(db, key) for key in SWITCH_KEYS]


@router.put("/switches/{key}")
def update_switch(
    key: SwitchKey, body: RuntimeSwitchUpdate, admin: AdminPrincipal = Depends(current_admin),
    db: Session = Depends(get_db),
) -> RuntimeSwitchOut:
    if admin.role != "ADMIN":
        raise APIError(403, "FORBIDDEN", "Only an ADMIN can pause or resume AI or auto-publish")
    before = switch_row(db, key)
    was_enabled = True if before is None else before.enabled
    note = body.note.strip() if body.note and body.note.strip() else None
    set_switch(db, key, body.enabled, admin.email, note)
    _write_audit_event(
        db, admin.email, "RUNTIME_SWITCH_CHANGED", "runtime_switch", uuid5(NAMESPACE_URL, f"runtime_switch:{key}"),
        {"key": key, "from": was_enabled, "to": body.enabled, "note": note},
    )
    db.commit()
    return _switch_out(db, key)


@router.get("/briefs/recent")
def list_recent_briefs(db: Session = Depends(get_db)) -> list[AdminAutoBriefOut]:
    """ADR-019: briefs the lane auto-approved in the last 24 hours, newest first."""
    events = db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.actor == BRIEF_ACTOR,
            AuditEvent.action == "STORY_AUTO_APPROVED",
            AuditEvent.created_at >= datetime.now(UTC) - timedelta(hours=24),
        )
        .order_by(AuditEvent.created_at.desc())
    ).all()
    out: list[AdminAutoBriefOut] = []
    for event in events:
        story = db.get(Story, event.entity_id)
        if story is None:
            continue
        en = db.scalars(
            select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "en")
        ).first()
        titles = db.scalars(
            select(SourceItem.title)
            .join(StorySource, StorySource.source_item_id == SourceItem.id)
            .where(StorySource.story_id == story.id)
            .order_by(StorySource.evidence_rank)
        ).all()
        out.append(
            AdminAutoBriefOut(
                story_id=story.id, status=story.status,
                headline=en.headline if en else None, summary=en.summary if en else None,
                source_titles=[t for t in titles if t],
                matched_tokens=(event.metadata_ or {}).get("title_match", {}).get("matched", []),
                approved_at=event.created_at,
            )
        )
    return out


def _review_task_out(task: ReviewTask) -> ReviewQueueItemOut:
    return ReviewQueueItemOut(
        id=task.id, story_id=task.story_id, reason=task.reason, status=task.status,
        decision=task.decision, created_at=task.created_at,
    )


def _get_story_or_404(db: Session, story_id: UUID, *, lock: bool = False) -> Story:
    story = db.scalars(select(Story).where(Story.id == story_id).with_for_update()).first() if lock else db.get(Story, story_id)
    if story is None:
        raise APIError(404, "STORY_NOT_FOUND", f"No story with id '{story_id}'")
    return story


def _require_status(story: Story, *allowed: str) -> None:
    if story.status not in allowed:
        raise APIError(
            409,
            "ILLEGAL_TRANSITION",
            f"Cannot act on a story in status '{story.status}' — requires one of {', '.join(allowed)}",
        )


def _resolve_review_task(db: Session, story_id: UUID, decision: str) -> None:
    task = db.scalars(
        select(ReviewTask).where(ReviewTask.story_id == story_id, ReviewTask.status == "PENDING")
    ).first()
    if task is not None:
        task.status = decision
        task.decision = decision


def _get_variant(db: Session, story_id: UUID, language: str) -> StoryVariant | None:
    return db.scalars(
        select(StoryVariant).where(StoryVariant.story_id == story_id, StoryVariant.language == language)
    ).first()


def _story_text_hash(variant: StoryVariant | None) -> str:
    payload = "" if variant is None else f"{variant.headline}\n{variant.summary}\n{variant.why_matters or ''}"
    return hashlib.sha256(payload.encode()).hexdigest()


@router.get("/review-queue")
def get_review_queue(
    cursor: str | None = None,
    limit: int = 50,
    danger_only: bool = False,
    reason: str | None = None,
    q: str | None = None,
    topic: str | None = None,
    source_id: UUID | None = None,
    telugu: TeluguFilter | None = None,
    older_than_hours: int | None = None,
    db: Session = Depends(get_db),
) -> ReviewQueuePageOut:
    """Review 2026-09-30 R7: paged; always-human-reviewed reasons first, then oldest."""
    return ReviewQueuePageOut(**review_queue(
        db, now=datetime.now(UTC), cursor=cursor, limit=limit, danger_only=danger_only, reason=reason, q=q,
        topic=topic, source_id=source_id, telugu=telugu, older_than_hours=older_than_hours,
    ))


@router.get("/stories")
def list_stories(
    status: StoryStatus | None = None,
    corrected: bool = False,
    q: str | None = None,
    topic: str | None = None,
    source_id: UUID | None = None,
    telugu: TeluguFilter | None = None,
    format: StoryFormat | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> AdminStoryListOut:
    """Review 2026-09-30 R7: the content library, every status, newest activity first."""
    return AdminStoryListOut(**story_library(
        db, now=datetime.now(UTC), status=status, corrected=corrected, q=q, topic=topic, source_id=source_id,
        telugu=telugu, format=format, limit=limit, offset=offset,
    ))


@router.get("/stories/{story_id}")
def get_story_detail(story_id: UUID, db: Session = Depends(get_db)) -> AdminStoryDetailOut:
    story = _get_story_or_404(db, story_id)

    variants = db.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id)).all()
    links = db.scalars(
        select(StorySource).where(StorySource.story_id == story.id).order_by(StorySource.evidence_rank)
    ).all()
    sources_out: list[AdminStorySourceOut] = []
    for link in links:
        item = db.get(SourceItem, link.source_item_id)
        if item is None:
            continue
        source = db.get(Source, item.source_id)
        sources_out.append(
            AdminStorySourceOut(
                role=link.role,
                url=item.url,
                title=item.title,
                published_at=item.published_at,
                source_name=source.name if source else "unknown",
                source_rights_status=source.rights_status if source else "DISABLED",
                description=item.description,
            )
        )

    review_task = db.scalars(
        select(ReviewTask).where(ReviewTask.story_id == story.id).order_by(ReviewTask.created_at.desc())
    ).first()
    corrections = db.scalars(
        select(Correction).where(Correction.story_id == story.id).order_by(Correction.created_at.desc())
    ).all()

    return AdminStoryDetailOut(
        id=story.id,
        canonical_slug=story.canonical_slug,
        status=story.status,
        sensitivity=story.sensitivity,
        format=story.format,
        importance=story.importance,
        importance_override=story.importance_override,  # type: ignore[arg-type]
        classification_confidence=story.classification_confidence,
        published_at=story.published_at,
        variants={
            v.language: StoryVariantOut(
                language=v.language, headline=v.headline, summary=v.summary,
                why_matters=v.why_matters, qa_status=v.qa_status,
            )
            for v in variants
        },
        telugu_repair=_telugu_repair_info(db, story, variants),
        topics=sorted(db.scalars(
            select(Topic.slug).join(StoryTopic, StoryTopic.topic_id == Topic.id).where(StoryTopic.story_id == story.id)
        ).all()),
        countries=event_countries_many(db, [story.id])[story.id],
        sources=sources_out,
        review_task=_review_task_out(review_task) if review_task else None,
        corrections=[
            AdminCorrectionOut(
                id=c.id, reason=c.reason, old_text_hash=c.old_text_hash,
                new_text_hash=c.new_text_hash, created_at=c.created_at,
            )
            for c in corrections
        ],
    )


_CONTENT_RULE_MESSAGES = {
    SUMMARY_REPEATS_HEADLINE: "the summary repeats the headline",
    SUMMARY_TOO_SHORT: f"the summary needs at least {MIN_SUMMARY_SENTENCES} sentences or {MIN_SUMMARY_WORDS} words",
    HEADLINE_COPIES_SOURCE: "the headline is too close to a source's own title",
}


def _require_publishable_content(db: Session, story: Story) -> None:
    """ADR-026: the same rules as automatic approval and publication."""
    if failures := validate_for_publication(db, story):
        raise APIError(
            422,
            "CONTENT_RULES_FAILED",
            "Can't publish yet: " + "; ".join(_CONTENT_RULE_MESSAGES[f] for f in failures) + f" ({', '.join(failures)})",
        )


@router.post("/stories/{story_id}/approve")
def approve_story(
    story_id: UUID, body: AdminActionRequest, admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)
) -> AdminActionResponse:
    story = _get_story_or_404(db, story_id)
    _require_status(story, "REVIEW_REQUIRED")
    en = _get_variant(db, story.id, "en")
    if en is None or not en.headline.strip() or not en.summary.strip():
        raise APIError(
            422, "NO_ENGLISH_DRAFT", "Write an English headline and summary before approving — English is canonical"
        )
    _require_publishable_content(db, story)
    # Review 2026-09-29 #7: rights are rechecked at approval, not only ingest.
    if blocked := unpermitted_sources(db, story.id):
        raise APIError(
            409,
            "SOURCE_RIGHTS_REVOKED",
            "A source behind this story is no longer approved for publication: "
            + ", ".join(f"{s.name} ({s.rights_status})" for s in blocked),
        )

    story.status = "APPROVED"
    db.flush()
    story.status = "SCHEDULED"
    db.flush()

    _resolve_review_task(db, story.id, "APPROVED")
    _write_audit_event(db, admin.email, "STORY_APPROVED", "story", story.id, {"reason": body.reason})
    db.commit()
    db.refresh(story)
    return AdminActionResponse(story_id=story.id, status=story.status)


@router.put("/stories/{story_id}/variants/{language}")
def write_story_draft(
    story_id: UUID,
    language: Language,
    body: AdminDraftRequest,
    admin: AdminPrincipal = Depends(current_admin),
    db: Session = Depends(get_db),
) -> AdminActionResponse:
    """Editor-written draft for a story still in review: the fallback when no
    AI route may draft it (NO_PAID_PROVIDER, budget exhausted, outage).
    Published stories go through /correct instead, which records a
    Correction. English stays canonical (NON_NEGOTIABLES #7): Telugu needs an
    English variant to derive from, must pass the same QA as machine
    translation, and is invalidated whenever the English is rewritten."""

    story = _get_story_or_404(db, story_id, lock=True)
    _require_status(story, "REVIEW_REQUIRED")

    headline = body.headline.strip()
    summary = body.summary.strip()
    why_matters = body.why_matters.strip() if body.why_matters and body.why_matters.strip() else None
    if not headline or not summary:
        raise APIError(422, "EMPTY_DRAFT", "Headline and summary must not be blank")

    en = _get_variant(db, story.id, "en")
    if language == "te":
        if en is None:
            raise APIError(409, "NO_ENGLISH_DRAFT", "Write the English draft first — Telugu is derived from it")
        issues = find_variant_qa_issues((en.headline, en.summary, en.why_matters), (headline, summary, why_matters))
        if issues:
            raise APIError(422, "TELUGU_QA_FAILED", f"Telugu draft doesn't match the English: {', '.join(issues)}")

    variant = en if language == "en" else _get_variant(db, story.id, "te")
    old_hash = _story_text_hash(variant)
    if variant is None:
        variant = StoryVariant(story_id=story.id, language=language, headline=headline, summary=summary)
        db.add(variant)
    variant.headline = headline
    variant.summary = summary
    variant.why_matters = why_matters
    variant.model_version = EDITOR_MODEL_VERSION
    # English has no QA pass of its own; Telugu reaching here passed QA above.
    variant.qa_status = "PASSED" if language == "te" else "PENDING"
    variant.generated_at = datetime.now(UTC)

    if language == "en":
        db.execute(delete(StoryWhyMattersCache).where(StoryWhyMattersCache.story_id == story.id))
        te = _get_variant(db, story.id, "te")
        if te is not None:
            db.delete(te)
    db.flush()

    _write_audit_event(
        db, admin.email, "STORY_DRAFT_WRITTEN", "story", story.id,
        {"language": language, "reason": body.reason, "old_text_hash": old_hash, "new_text_hash": _story_text_hash(variant)},
    )
    db.commit()
    db.refresh(story)
    return AdminActionResponse(story_id=story.id, status=story.status)


@router.put("/stories/{story_id}/topics")
def set_story_topics(
    story_id: UUID,
    body: AdminTopicsRequest,
    admin: AdminPrincipal = Depends(current_admin),
    db: Session = Depends(get_db),
) -> AdminActionResponse:
    """Editor-set topics (review #11). AI classification tags the stories it
    drafts; an editor-drafted story has no other way to get a topic, so it
    never appears on a topic page. Only existing active topics: editors pick
    from the taxonomy, they don't grow it. Topics are navigation metadata,
    not story text, so this works in any status without a Correction."""

    story = _get_story_or_404(db, story_id)
    slugs = list(dict.fromkeys(s.strip() for s in body.topics if s.strip()))
    topics = db.scalars(select(Topic).where(Topic.slug.in_(slugs), Topic.active.is_(True))).all() if slugs else []
    unknown = sorted(set(slugs) - {t.slug for t in topics})
    if unknown:
        raise APIError(422, "UNKNOWN_TOPIC", f"Not an active topic: {', '.join(unknown)}")

    old = sorted(db.scalars(
        select(Topic.slug).join(StoryTopic, StoryTopic.topic_id == Topic.id).where(StoryTopic.story_id == story.id)
    ).all())
    db.execute(delete(StoryTopic).where(StoryTopic.story_id == story.id))
    for topic in topics:
        db.add(StoryTopic(story_id=story.id, topic_id=topic.id, weight=1))
    db.flush()

    recompute_importance(db, story)  # ADR-027: priority topics score higher

    _write_audit_event(
        db, admin.email, "STORY_TOPICS_SET", "story", story.id,
        {"old": old, "new": sorted(slugs), "reason": body.reason},
    )
    db.commit()
    return AdminActionResponse(story_id=story.id, status=story.status)


@router.put("/stories/{story_id}/countries")
def set_story_countries(
    story_id: UUID,
    body: AdminCountriesRequest,
    admin: AdminPrincipal = Depends(current_admin),
    db: Session = Depends(get_db),
) -> AdminActionResponse:
    """ADR-027: where the story happens. Generation stores the model's
    countries; editors correct them, and set them for a hand-drafted story.
    Supported codes only. Like topics, this is metadata, not story text."""

    story = _get_story_or_404(db, story_id)
    requested = list(dict.fromkeys(c.strip() for c in body.countries if c.strip()))
    codes = normalize_countries(requested)
    unknown = [c for c in requested if normalize_country(c) is None]
    if unknown:
        raise APIError(422, "UNKNOWN_COUNTRY", f"Not a supported country: {', '.join(unknown)}")

    old = event_countries_many(db, [story.id])[story.id]
    set_event_countries(db, story.id, codes)
    _write_audit_event(
        db, admin.email, "STORY_COUNTRIES_SET", "story", story.id,
        {"old": old, "new": sorted(codes), "reason": body.reason},
    )
    db.commit()
    return AdminActionResponse(story_id=story.id, status=story.status)


@router.put("/stories/{story_id}/importance")
def set_story_importance(
    story_id: UUID,
    body: AdminImportanceRequest,
    admin: AdminPrincipal = Depends(current_admin),
    db: Session = Depends(get_db),
) -> AdminActionResponse:
    """ADR-027: an editor's Low/Normal/High takes precedence over the
    computed score; null clears it and recomputes."""

    story = _get_story_or_404(db, story_id)
    old = {"level": story.importance_override, "importance": story.importance}
    story.importance_override = body.level
    recompute_importance(db, story)
    _write_audit_event(
        db, admin.email, "STORY_IMPORTANCE_SET", "story", story.id,
        {"old": old, "new": {"level": body.level, "importance": story.importance}, "reason": body.reason},
    )
    db.commit()
    return AdminActionResponse(story_id=story.id, status=story.status)


@router.post("/stories/{story_id}/reject")
def reject_story(
    story_id: UUID, body: AdminRejectRequest, admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)
) -> AdminActionResponse:
    story = _get_story_or_404(db, story_id)
    _require_status(story, "REVIEW_REQUIRED")

    story.status = "ARCHIVED" if body.archive else "DRAFT"
    db.flush()

    _resolve_review_task(db, story.id, "REJECTED")
    _write_audit_event(
        db, admin.email, "STORY_REJECTED", "story", story.id, {"reason": body.reason, "outcome": story.status}
    )
    db.commit()
    db.refresh(story)
    return AdminActionResponse(story_id=story.id, status=story.status)


# ADR-025: an ADMIN can send a held story back through the AI a bounded
# number of times, audited. It re-enters normal generation and review
# routing, so review is never bypassed.
AI_RETRY_RESET_ACTION = "AI_RETRY_RESET"
MAX_AI_RETRY_RESETS = 2
# Review reasons that mean "the AI couldn't finish", as opposed to an
# editorial hold (sensitivity, confidence, content rules).
_AI_HOLD_REASONS = ("AI_RETRIES_EXHAUSTED", "NO_PAID_PROVIDER")


def _resets_used(db: Session, story_id: UUID, stage: str) -> int:
    return ai_retry.manual_resets_used(db, story_id, stage)


def _telugu_repair_info(db: Session, story: Story, variants: Sequence[StoryVariant]) -> AdminTeluguRepairOut:
    en = next((v for v in variants if v.language == "en"), None)
    te = next((v for v in variants if v.language == "te"), None)
    left = max(0, MAX_AI_RETRY_RESETS - _resets_used(db, story.id, ai_retry.STAGE_TRANSLATE))
    return AdminTeluguRepairOut(
        qa_issues=find_variant_qa_issues(
            (en.headline, en.summary, en.why_matters), (te.headline, te.summary, te.why_matters)
        ) if en and te else [],
        english_text_hash=_story_text_hash(en) if en else None,
        telugu_text_hash=_story_text_hash(te) if te else None,
        resets_left=left,
        can_regenerate=bool(en and te and te.qa_status == "FAILED" and left and story.status in TRANSLATABLE_STATUSES),
    )


@router.post("/stories/{story_id}/repair-telugu")
def repair_telugu(
    story_id: UUID, body: AdminTeluguRepairRequest,
    admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db),
) -> AdminActionResponse:
    if admin.role != "ADMIN":
        raise APIError(403, "FORBIDDEN", "Only an ADMIN can repair Telugu variants")
    reason = body.reason.strip()
    if not reason:
        raise APIError(422, "REASON_REQUIRED", "Enter a reason for this translation repair")
    story = _get_story_or_404(db, story_id, lock=True)
    en, te = _get_variant(db, story.id, "en"), _get_variant(db, story.id, "te")
    if en is None:
        raise APIError(409, "NO_ENGLISH_DRAFT", "English is required before repairing Telugu")
    if te is None:
        raise APIError(409, "NO_TELUGU_VARIANT", "No existing Telugu variant to repair; reload this story")
    info = _telugu_repair_info(db, story, [en, te])
    if body.english_text_hash != info.english_text_hash or body.telugu_text_hash != info.telugu_text_hash:
        raise APIError(409, "STALE_VARIANT", "Story text changed; reload and review the latest text before repairing")
    metadata = {
        "reason": reason, "qa_issues": info.qa_issues, "previous_qa_status": te.qa_status,
        "english_text_hash": info.english_text_hash, "telugu_text_hash": info.telugu_text_hash,
    }
    if body.action == "withhold":
        if te.qa_status != "FAILED":
            te.qa_status = "FAILED"
            _write_audit_event(db, admin.email, "TELUGU_VARIANT_WITHHELD", "story", story.id,
                               {**metadata, "new_qa_status": "FAILED"})
    else:
        _require_status(story, *TRANSLATABLE_STATUSES)
        if te.qa_status != "FAILED":
            raise APIError(409, "VARIANT_NOT_WITHHELD", "Withhold the Telugu variant before requesting regeneration")
        if info.resets_left == 0:
            raise APIError(409, "RETRY_LIMIT_REACHED", "The two manual translation resets are used; no regeneration requested")
        state = db.scalars(select(AiWorkState).where(
            AiWorkState.story_id == story.id, AiWorkState.stage == ai_retry.STAGE_TRANSLATE,
        )).first()
        if state is not None:
            db.delete(state)
        db.delete(te)
        _write_audit_event(db, admin.email, AI_RETRY_RESET_ACTION, "story", story.id, {
            **metadata, "stage": ai_retry.STAGE_TRANSLATE, "origin": "telugu_repair",
            "reset_number": MAX_AI_RETRY_RESETS - info.resets_left + 1,
        })
    db.commit()
    return AdminActionResponse(story_id=story.id, status=cast(StoryStatus, story.status))


@router.get("/ai-holds")
def list_ai_holds(admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)) -> list[AdminAiHoldOut]:
    """Every story stage whose AI retries ran out, newest first. Exhausted
    translations are otherwise invisible: the story keeps serving English."""
    states = db.scalars(
        select(AiWorkState).where(AiWorkState.failure_class == "EXHAUSTED").order_by(AiWorkState.updated_at.desc())
    ).all()
    out = []
    for state in states:
        story = db.get(Story, state.story_id)
        if story is None:
            continue
        en = _get_variant(db, story.id, "en")
        used = _resets_used(db, story.id, state.stage)
        out.append(
            AdminAiHoldOut(
                story_id=story.id, stage=state.stage, story_status=story.status,
                headline=en.headline if en else None, last_status=state.last_status, updated_at=state.updated_at,
                resets_used=used, resets_left=max(0, MAX_AI_RETRY_RESETS - used),
            )
        )
    return out


@router.post("/stories/{story_id}/retry-ai")
def retry_ai(
    story_id: UUID, body: AdminRetryAiRequest, admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)
) -> AdminActionResponse:
    if admin.role != "ADMIN":
        raise APIError(403, "FORBIDDEN", "Only an ADMIN can retry AI on a held story")
    story = _get_story_or_404(db, story_id, lock=True)
    state = db.scalars(
        select(AiWorkState).where(AiWorkState.story_id == story.id, AiWorkState.stage == body.stage)
    ).first()

    if body.stage == ai_retry.STAGE_GENERATE:
        _require_status(story, "REVIEW_REQUIRED")
        task = db.scalars(
            select(ReviewTask).where(ReviewTask.story_id == story.id, ReviewTask.status == "PENDING")
        ).first()
        held_by_ai = task is not None and any(r in task.reason for r in _AI_HOLD_REASONS)
        if not held_by_ai and (state is None or state.failure_class != "EXHAUSTED"):
            raise APIError(409, "NOT_AI_HELD", "This story isn't waiting on the AI — approve, edit or reject it instead")
    elif state is None or state.failure_class != "EXHAUSTED":
        raise APIError(409, "NOT_AI_HELD", "This story's translation hasn't run out of AI retries")

    used = _resets_used(db, story.id, body.stage)
    if used >= MAX_AI_RETRY_RESETS:
        raise APIError(
            409, "RETRY_LIMIT_REACHED",
            f"AI has already been retried {used} times for this story — write it by hand or reject it",
        )

    if state is not None:
        db.delete(state)
    if body.stage == ai_retry.STAGE_GENERATE:
        story.status = "DRAFT"
        db.flush()
        items = db.scalars(
            select(SourceItem).join(StorySource, StorySource.source_item_id == SourceItem.id)
            .where(StorySource.story_id == story.id)
        ).all()
        for item in items:
            item.ingest_status = "CLUSTERED"
        _resolve_review_task(db, story.id, "REJECTED")
    db.flush()

    _write_audit_event(
        db, admin.email, AI_RETRY_RESET_ACTION, "story", story.id,
        {"stage": body.stage, "reason": body.reason, "reset_number": used + 1},
    )
    db.commit()
    db.refresh(story)
    return AdminActionResponse(story_id=story.id, status=story.status)


@router.post("/stories/{story_id}/retract")
def retract_story(
    story_id: UUID, body: AdminActionRequest, admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)
) -> AdminActionResponse:
    story = _get_story_or_404(db, story_id)
    _require_status(story, "PUBLISHED")

    story.status = "RETRACTED"
    db.flush()

    _write_audit_event(db, admin.email, "STORY_RETRACTED", "story", story.id, {"reason": body.reason})
    db.commit()
    db.refresh(story)
    return AdminActionResponse(story_id=story.id, status=story.status)


@router.post("/stories/{story_id}/approve-breaking-alert")
def approve_breaking_alert(
    story_id: UUID, body: AdminActionRequest, admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)
) -> AdminActionResponse:
    """T17: the "never auto-sent" gate for a `BREAKING_ALERT` push — separate
    from, and in addition to, the publish approval NON_NEGOTIABLES #5
    already required for a `sensitivity == 'BREAKING'` story to reach
    PUBLISHED. `notification_dispatch` (app/jobs/notify.py) only ever
    considers a story for a breaking push once `breaking_alert_approved_at`
    is set here."""

    story = _get_story_or_404(db, story_id)
    _require_status(story, "PUBLISHED", "UPDATED")
    if story.sensitivity != "BREAKING":
        raise APIError(422, "NOT_BREAKING", "Only a BREAKING-sensitivity story can have a breaking alert approved")

    story.breaking_alert_approved_at = datetime.now(UTC)
    db.flush()
    _write_audit_event(db, admin.email, "BREAKING_ALERT_APPROVED", "story", story.id, {"reason": body.reason})
    db.commit()
    db.refresh(story)
    return AdminActionResponse(story_id=story.id, status=story.status)


@router.post("/stories/{story_id}/correct")
def correct_story(
    story_id: UUID, body: AdminCorrectionRequest, admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)
) -> AdminActionResponse:
    story = _get_story_or_404(db, story_id, lock=True)
    _require_status(story, "PUBLISHED", "UPDATED")

    if body.headline is None and body.summary is None and body.why_matters is None:
        raise APIError(422, "NO_CHANGES", "At least one of headline/summary/why_matters must be provided")

    variant = db.scalars(
        select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "en")
    ).first()
    if variant is None:
        raise APIError(404, "VARIANT_NOT_FOUND", "No English story variant to correct")

    old_hash = _story_text_hash(variant)
    if body.headline is not None:
        variant.headline = body.headline
    if body.summary is not None:
        variant.summary = body.summary
    if body.why_matters is not None:
        variant.why_matters = body.why_matters
    variant.qa_status = "PENDING"
    variant.generated_at = datetime.now(UTC)
    db.execute(delete(StoryWhyMattersCache).where(StoryWhyMattersCache.story_id == story.id))
    db.flush()
    _require_publishable_content(db, story)
    new_hash = _story_text_hash(variant)

    if story.status == "PUBLISHED":
        story.status = "UPDATED"
        db.flush()
    else:  # UPDATED -> CORRECTION_PENDING -> UPDATED, per the ticket's literal transition text
        story.status = "CORRECTION_PENDING"
        db.flush()
        story.status = "UPDATED"
        db.flush()

    # Telugu-variant invalidation hook (T13 owns regeneration): an approved
    # English correction invalidates the existing derived variant per
    # NON_NEGOTIABLES #7 — deleting it forces regeneration rather than
    # leaving stale Telugu text live against a corrected English original.
    te_variant = db.scalars(
        select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "te")
    ).first()
    if te_variant is not None:
        db.delete(te_variant)

    db.add(
        Correction(
            story_id=story.id,
            reason=body.reason,
            old_text_hash=old_hash,
            new_text_hash=new_hash,
            created_by=UUID(admin.user_id),
        )
    )
    _write_audit_event(
        db, admin.email, "STORY_CORRECTED", "story", story.id,
        {"reason": body.reason, "old_text_hash": old_hash, "new_text_hash": new_hash},
    )
    db.commit()
    db.refresh(story)
    return AdminActionResponse(story_id=story.id, status=story.status)


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db)) -> list[AdminJobOut]:
    jobs = db.scalars(select(Job).order_by(Job.run_after.desc()).limit(100)).all()
    return [
        AdminJobOut(
            id=job.id,
            type=job.type,
            status=job.status,
            attempts=job.attempts,
            run_after=job.run_after,
            locked_at=job.locked_at,
            last_error=job.last_error,
        )
        for job in jobs
    ]


@router.get("/observability")
def get_observability(db: Session = Depends(get_db)) -> ObservabilityOut:
    """T18: the one admin surface for "is the pipeline healthy and what is
    it costing" — ingestion health, job queue state, and AI spend vs.
    budget, all scoped to what an editor needs to see in the last 24h."""
    now = datetime.now(UTC)
    since_24h = now - timedelta(hours=24)

    # Aggregated in Python rather than via a SQL GROUP BY on a JSONB `->>`
    # expression: Postgres requires the GROUP BY expression to be
    # syntactically identical to the selected one, which SQLAlchemy's JSONB
    # comparator doesn't reliably produce — and this table is small enough
    # (recent source_fetch jobs only) that it doesn't matter.
    recent_fetch_jobs = db.scalars(
        select(Job).where(
            Job.type == "source_fetch", Job.run_after >= since_24h, Job.status.in_(["DONE", "FAILED"])
        )
    ).all()
    counts_by_source: dict[str, dict[str, int]] = {}
    for job in recent_fetch_jobs:
        source_id = job.payload.get("source_id") if isinstance(job.payload, dict) else None
        if source_id is None:
            continue
        counts_by_source.setdefault(source_id, {})[job.status] = counts_by_source.get(source_id, {}).get(job.status, 0) + 1

    sources = db.scalars(select(Source).order_by(Source.name)).all()
    ingestion_health = [
        SourceIngestionHealthOut(
            source_id=source.id,
            source_name=source.name,
            success_count_24h=counts_by_source.get(str(source.id), {}).get("DONE", 0),
            failure_count_24h=counts_by_source.get(str(source.id), {}).get("FAILED", 0),
            fail_count=source.fail_count,
            circuit_breaker_tripped=source.fail_count >= CIRCUIT_BREAKER_THRESHOLD,
            last_success_at=source.last_success_at,
            last_error_at=source.last_error_at,
        )
        for source in sources
    ]

    status_rows = db.execute(select(Job.status, func.count()).group_by(Job.status)).all()
    oldest_pending = db.scalar(select(func.min(Job.run_after)).where(Job.status == "PENDING"))
    job_queue = JobQueueHealthOut(
        counts_by_status=dict(status_rows),
        oldest_pending_age_seconds=(now - oldest_pending).total_seconds() if oldest_pending else None,
    )

    monthly_budget = os.environ.get("MONTHLY_AI_BUDGET_USD")
    hard_cap = os.environ.get("MONTHLY_AI_HARD_CAP_USD")
    daily_alert = os.environ.get("DAILY_AI_ALERT_USD")
    mtd = month_to_date_cost_usd(db, now)
    ai_cost = AiCostSummaryOut(
        month_to_date_cost_usd=mtd,
        monthly_budget_usd=float(monthly_budget) if monthly_budget else None,
        monthly_budget_remaining_usd=(float(monthly_budget) - mtd) if monthly_budget else None,
        today_cost_usd=today_cost_usd(db, now),
        daily_alert_usd=float(daily_alert) if daily_alert else None,
        over_monthly_budget=is_over_monthly_budget(db, now),
        monthly_hard_cap_usd=float(hard_cap) if hard_cap else None,
        hard_cap_remaining_usd=(float(hard_cap) - mtd) if hard_cap else None,
        mode=budget_mode(mtd),
        **reporting_windows(now),
        rows=[AiCostRowOut(**row) for row in cost_by_task_and_day(db)],
    )

    x_monthly_budget = os.environ.get("MONTHLY_X_API_BUDGET_USD")
    x_mtd = x_month_to_date_cost_usd(db, now)
    x_over_budget = x_is_over_monthly_budget(db, now)
    low_priority_paused = 0
    if x_over_budget:
        x_accounts = db.scalars(select(XAccount)).all()
        low_priority_paused = sum(1 for account in x_accounts if is_low_priority(account))
    x_cost = XCostSummaryOut(
        month_to_date_cost_usd=x_mtd,
        monthly_budget_usd=float(x_monthly_budget) if x_monthly_budget else None,
        monthly_budget_remaining_usd=(float(x_monthly_budget) - x_mtd) if x_monthly_budget else None,
        over_monthly_budget=x_over_budget,
        low_priority_accounts_paused=low_priority_paused,
    )

    operations = [OpsCheckOut(**vars(status)) for status in ops_statuses(db, now)]

    return ObservabilityOut(
        ingestion_health=ingestion_health, job_queue=job_queue, ai_cost=ai_cost, x_cost=x_cost, operations=operations
    )


@router.get("/ai-costs")
def get_ai_costs(start: date | None = None, end: date | None = None, db: Session = Depends(get_db)) -> AiCostReportOut:
    """Review 2026-09-30 R5: AI spend over inclusive UTC days (default: the
    month to date), bounded so the aggregate stays cheap."""
    today = datetime.now(UTC).date()
    end = end or today
    start = start or end.replace(day=1)
    if start > end:
        raise APIError(422, "INVALID_RANGE", "start must be on or before end")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise APIError(422, "RANGE_TOO_LONG", f"A range covers at most {MAX_RANGE_DAYS} days")
    return AiCostReportOut(**cost_report(db, start, end))


@router.get("/coverage")
def get_coverage(start: date | None = None, end: date | None = None, db: Session = Depends(get_db)) -> CoverageReportOut:
    """Review 2026-09-30 R8: what each feed sends vs. what reaches readers,
    by publisher and topic, over inclusive UTC days (default: last 7)."""
    end = end or datetime.now(UTC).date()
    start = start or end - timedelta(days=6)
    if start > end:
        raise APIError(422, "INVALID_RANGE", "start must be on or before end")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise APIError(422, "RANGE_TOO_LONG", f"A range covers at most {MAX_RANGE_DAYS} days")
    return CoverageReportOut(**coverage_report(db, start, end))


@router.get("/pipeline")
def get_pipeline(db: Session = Depends(get_db)) -> PipelineStatusOut:
    """Review 2026-09-30 R5: stage counts and the oldest wait at each stage."""
    return PipelineStatusOut(**pipeline_status(db, datetime.now(UTC)))


@router.get("/_debug/throw", include_in_schema=False)
def debug_throw() -> None:
    """T18 acceptance criteria: "a deliberately thrown error... surfaces in
    the error tracker with useful context". Admin-authed (via the router's
    `current_admin` dependency) so it can't be hit anonymously; exists only
    to prove request_id/actor context reaches `capture_exception` — see
    `tests/test_observability.py`."""
    raise RuntimeError("T18 debug throw — deliberate, for error-tracking verification")


@router.get("/audit")
def list_audit_events(
    cursor: str | None = None,
    limit: int = 100,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    actor: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    db: Session = Depends(get_db),
) -> AdminAuditPageOut:
    """Review 2026-09-30 R7: searchable, paged history (was the latest 200 only)."""
    return AdminAuditPageOut(**audit_history(
        db, cursor=cursor, limit=limit, action=action, entity_type=entity_type, entity_id=entity_id,
        actor=actor, since=since, until=until,
    ))


# --- ADR-029: reader reports ------------------------------------------------

REPORTS_MAX_LIMIT = 100


def _reader_report_out(db: Session, report: ReaderReport) -> AdminReaderReportOut:
    story = _get_story_or_404(db, report.story_id)
    variant = _get_variant(db, report.story_id, "en")
    resolver = db.get(User, report.resolved_by) if report.resolved_by else None
    return AdminReaderReportOut.model_validate({
        "id": report.id, "story_id": report.story_id, "story_slug": story.canonical_slug,
        "story_status": story.status, "story_headline": variant.headline if variant else None,
        "category": report.category, "description": report.description,
        "description_purged_at": report.description_purged_at, "language": report.language,
        "platform": report.platform, "sender": report.client_hash[:8], "repeat_count": report.repeat_count,
        "status": report.status, "resolution": report.resolution, "resolution_note": report.resolution_note,
        "resolved_by_email": resolver.email if resolver else None, "resolved_at": report.resolved_at,
        "correction_id": report.correction_id, "created_at": report.created_at,
    })


def _get_report_or_404(db: Session, report_id: UUID) -> ReaderReport:
    report = db.get(ReaderReport, report_id)
    if report is None:
        raise APIError(404, "REPORT_NOT_FOUND", f"No reader report with id '{report_id}'")
    return report


@router.get("/reports")
def list_reader_reports(
    status: ReaderReportStatus | Literal["ALL"] = "OPEN",
    category: ReaderReportCategory | None = None,
    story_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> AdminReaderReportListOut:
    """Open reports oldest first (the next to handle); closed ones newest first."""
    limit = max(1, min(limit, REPORTS_MAX_LIMIT))
    offset = max(0, offset)
    filters = []
    if status != "ALL":
        filters.append(ReaderReport.status == status)
    if category is not None:
        filters.append(ReaderReport.category == category)
    if story_id is not None:
        filters.append(ReaderReport.story_id == story_id)
    order = ReaderReport.created_at.asc() if status == "OPEN" else ReaderReport.created_at.desc()
    reports = db.scalars(
        select(ReaderReport).where(*filters).order_by(order, ReaderReport.id).offset(offset).limit(limit)
    ).all()
    total = db.scalar(select(func.count()).select_from(ReaderReport).where(*filters))
    open_count = db.scalar(select(func.count()).select_from(ReaderReport).where(ReaderReport.status == "OPEN"))
    return AdminReaderReportListOut(
        items=[_reader_report_out(db, report) for report in reports], total=int(total or 0), open_count=int(open_count or 0)
    )


@router.get("/reports/{report_id}")
def get_reader_report(report_id: UUID, db: Session = Depends(get_db)) -> AdminReaderReportOut:
    return _reader_report_out(db, _get_report_or_404(db, report_id))


@router.post("/reports/{report_id}/resolve")
def resolve_reader_report(
    report_id: UUID,
    body: AdminReaderReportResolveRequest,
    admin: AdminPrincipal = Depends(current_admin),
    db: Session = Depends(get_db),
) -> AdminReaderReportOut:
    report = _get_report_or_404(db, report_id)
    try:
        resolve_report(
            db, report, resolution=body.resolution, note=body.note, correction_id=body.correction_id,
            actor_email=admin.email, actor_id=UUID(admin.user_id), now=datetime.now(UTC),
        )
    except ResolveError as exc:
        raise APIError(exc.status, exc.code, exc.message) from exc
    db.refresh(report)
    return _reader_report_out(db, report)
