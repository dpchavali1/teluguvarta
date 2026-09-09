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
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.budget import (
    cost_by_task_and_day,
    is_over_monthly_budget,
    month_to_date_cost_usd,
    today_cost_usd,
)
from app.auth import AdminPrincipal, current_admin
from app.db import get_db
from app.errors import APIError
from app.jobs.source_fetch import CIRCUIT_BREAKER_THRESHOLD
from app.models import (
    AuditEvent,
    Correction,
    Job,
    PilotSignup,
    ReviewTask,
    Source,
    SourceItem,
    Story,
    StorySource,
    StoryVariant,
    XAccount,
)
from app.rate_limit import rate_limit_admin
from app.schemas import (
    AdminActionRequest,
    AdminActionResponse,
    AdminAuditEventOut,
    AdminCorrectionOut,
    AdminCorrectionRequest,
    AdminJobOut,
    AdminPilotSignupOut,
    AdminPilotSignupsResponse,
    AdminRejectRequest,
    AdminSourceCreate,
    AdminSourceOut,
    AdminSourceUpdate,
    AdminStoryDetailOut,
    AdminStorySourceOut,
    AdminXAccountCreate,
    AdminXAccountOut,
    AdminXAccountUpdate,
    AiCostRowOut,
    AiCostSummaryOut,
    JobQueueHealthOut,
    KillSwitchesOut,
    ObservabilityOut,
    ReviewQueueItemOut,
    RightsEvidence,
    SourceIngestionHealthOut,
    StoryVariantOut,
    XCostSummaryOut,
)
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
        refresh_minutes=source.refresh_minutes,
        active=source.active,
        fail_count=source.fail_count,
        last_success_at=source.last_success_at,
        last_error_at=source.last_error_at,
    )


@router.get("/sources")
def list_sources(db: Session = Depends(get_db)) -> list[AdminSourceOut]:
    sources = db.scalars(select(Source).order_by(Source.name)).all()
    return [_source_out(s) for s in sources]


@router.post("/sources", status_code=201)
def create_source(
    body: AdminSourceCreate, admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)
) -> AdminSourceOut:
    source = Source(
        name=body.name,
        base_url=body.base_url,
        feed_url=body.feed_url,
        source_type=body.source_type,
        country=body.country,
        language=body.language,
        refresh_minutes=body.refresh_minutes,
    )
    db.add(source)
    db.flush()
    _write_audit_event(db, admin.email, "SOURCE_CREATED", "source", source.id, {"name": source.name})
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
        raise APIError(
            422,
            "RIGHTS_TIER_NOT_ENABLED",
            f"'{new_rights_status}' is not enabled in this build phase — only DISABLED and LINK_ONLY "
            "are reachable per ADR-002",
        )

    if new_rights_status is not None and new_rights_status != "DISABLED" and new_rights_status != source.rights_status:
        if admin.role != "ADMIN":
            raise APIError(403, "FORBIDDEN", "Only an ADMIN can enable a source (move it off DISABLED)")
        merged: dict[str, Any] = {field: updates.get(field, getattr(source, field)) for field in REQUIRED_EVIDENCE_FIELDS}
        missing = [field for field, value in merged.items() if not value]
        if missing:
            raise APIError(
                422,
                "RIGHTS_EVIDENCE_REQUIRED",
                f"Cannot enable source: missing rights evidence field(s) {', '.join(missing)}",
            )

    for field, value in updates.items():
        setattr(source, field, value)
    if rights_evidence is not None:
        source.rights_evidence = rights_evidence

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
def get_kill_switches() -> KillSwitchesOut:
    return KillSwitchesOut(
        auto_publish_global=os.environ.get("AUTO_PUBLISH_GLOBAL", "false").lower() == "true",
        auto_publish_category_immigration=os.environ.get("AUTO_PUBLISH_CATEGORY_IMMIGRATION", "false").lower()
        == "true",
    )


def _review_task_out(task: ReviewTask) -> ReviewQueueItemOut:
    return ReviewQueueItemOut(
        id=task.id, story_id=task.story_id, reason=task.reason, status=task.status,
        decision=task.decision, created_at=task.created_at,
    )


def _get_story_or_404(db: Session, story_id: UUID) -> Story:
    story = db.get(Story, story_id)
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


def _story_text_hash(variant: StoryVariant | None) -> str:
    payload = "" if variant is None else f"{variant.headline}\n{variant.summary}\n{variant.why_matters or ''}"
    return hashlib.sha256(payload.encode()).hexdigest()


@router.get("/review-queue")
def get_review_queue(db: Session = Depends(get_db)) -> list[ReviewQueueItemOut]:
    tasks = db.scalars(
        select(ReviewTask).where(ReviewTask.status == "PENDING").order_by(ReviewTask.created_at)
    ).all()
    return [_review_task_out(task) for task in tasks]


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
        importance=story.importance,
        published_at=story.published_at,
        variants={
            v.language: StoryVariantOut(
                language=v.language, headline=v.headline, summary=v.summary,
                why_matters=v.why_matters, qa_status=v.qa_status,
            )
            for v in variants
        },
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


@router.post("/stories/{story_id}/approve")
def approve_story(
    story_id: UUID, body: AdminActionRequest, admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)
) -> AdminActionResponse:
    story = _get_story_or_404(db, story_id)
    _require_status(story, "REVIEW_REQUIRED")

    story.status = "APPROVED"
    db.flush()
    story.status = "SCHEDULED"
    db.flush()

    _resolve_review_task(db, story.id, "APPROVED")
    _write_audit_event(db, admin.email, "STORY_APPROVED", "story", story.id, {"reason": body.reason})
    db.commit()
    db.refresh(story)
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
    story = _get_story_or_404(db, story_id)
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
    db.flush()
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
    daily_alert = os.environ.get("DAILY_AI_ALERT_USD")
    mtd = month_to_date_cost_usd(db, now)
    ai_cost = AiCostSummaryOut(
        month_to_date_cost_usd=mtd,
        monthly_budget_usd=float(monthly_budget) if monthly_budget else None,
        monthly_budget_remaining_usd=(float(monthly_budget) - mtd) if monthly_budget else None,
        today_cost_usd=today_cost_usd(db, now),
        daily_alert_usd=float(daily_alert) if daily_alert else None,
        over_monthly_budget=is_over_monthly_budget(db, now),
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

    return ObservabilityOut(ingestion_health=ingestion_health, job_queue=job_queue, ai_cost=ai_cost, x_cost=x_cost)


@router.get("/pilot-signups")
def list_pilot_signups(db: Session = Depends(get_db)) -> AdminPilotSignupsResponse:
    """T20 pre-build validation gate: the opt-in count and roster behind the
    landing page's 3 example feeds — this table is the whole measurement of
    the gate's "opt-in" metric, see `docs/BUILD_ORDER.md`."""
    signups = db.scalars(select(PilotSignup).order_by(PilotSignup.created_at.desc())).all()
    return AdminPilotSignupsResponse(
        total=len(signups),
        items=[
            AdminPilotSignupOut(
                id=s.id,
                email=s.email,
                segment=s.segment,
                example_feed=s.example_feed,
                recommend_willingness=s.recommend_willingness,
                created_at=s.created_at,
            )
            for s in signups
        ],
    )


@router.get("/_debug/throw", include_in_schema=False)
def debug_throw() -> None:
    """T18 acceptance criteria: "a deliberately thrown error... surfaces in
    the error tracker with useful context". Admin-authed (via the router's
    `current_admin` dependency) so it can't be hit anonymously; exists only
    to prove request_id/actor context reaches `capture_exception` — see
    `tests/test_observability.py`."""
    raise RuntimeError("T18 debug throw — deliberate, for error-tracking verification")


@router.get("/audit")
def list_audit_events(db: Session = Depends(get_db)) -> list[AdminAuditEventOut]:
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(200)).all()
    return [
        AdminAuditEventOut(
            id=event.id, actor=event.actor, action=event.action, entity_type=event.entity_type,
            entity_id=event.entity_id, metadata=event.metadata_, created_at=event.created_at,
        )
        for event in events
    ]
