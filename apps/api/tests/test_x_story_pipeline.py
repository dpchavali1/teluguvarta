"""X3 acceptance tests: an X post carried through the *exact same* rights/
dedup/clustering/AI-classification/editorial pipeline as any other source
(§6.3.1, NON_NEGOTIABLES #4/#12) — no code path here is X-specific. X1/X2
already wired `XAdapter.emit()` onto the shared `SourceAdapter` contract
(`app/adapters/base.py`) and T09/T11/T12/T14 are source-agnostic by
construction (see `test_cluster.py`'s docstring); this file is the
end-to-end proof, run through the real jobs, that the claim actually holds
for an X-derived item rather than just being true "by inspection."
"""

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.adapters.x import XAdapter
from app.ai import gateway as gateway_module
from app.ai.providers.base import ProviderResponse
from app.content.serialize import story_to_out
from app.jobs.cluster import cluster_normalized_items
from app.jobs.generate import generate_stories
from app.jobs.publish import auto_publish_stories, publish_due_stories
from app.models import Source, SourceItem, Story, StorySource, XAccount

from .conftest import requires_postgres

pytestmark = requires_postgres


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
    monkeypatch.setattr(gateway_module, "_resolve_provider", lambda name: FakeProvider(responses))


def _classification(**overrides):
    base = {
        "relevant": True,
        "confidence": 0.9,
        "categories": ["Immigration Policy"],
        "countries": ["US"],
        "entities": ["USCIS"],
        "sensitivity": "NONE",
        "urgency": "NORMAL",
        "headline_en": "n/a",
        "summary_en": "n/a",
        "why_matters_en": "n/a",
        "claims": [],
        "source_refs": [],
        "publish_recommendation": "PUBLISH",
    }
    base.update(overrides)
    return base


def _generation(**overrides):
    base = {
        "relevant": True,
        "confidence": 0.9,
        "categories": [],
        "countries": [],
        "entities": [],
        "sensitivity": "NONE",
        "urgency": "NORMAL",
        "headline_en": "Agency announces new policy",
        "summary_en": "A federal agency announced a new policy affecting applicants this week.",
        "why_matters_en": "Applicants should review how this affects their case.",
        "claims": [{"text": "A new policy was announced", "source_refs": ["src-1"]}],
        "source_refs": ["src-1"],
        "publish_recommendation": "PUBLISH",
    }
    base.update(overrides)
    return base


def _make_x_source(db: Session, *, rights_status: str = "LINK_ONLY") -> tuple[Source, XAccount]:
    source = Source(name="Official Account", source_type="X_ACCOUNT", rights_status=rights_status, active=True)
    db.add(source)
    db.flush()
    x_account = XAccount(source_id=source.id, x_user_id="12345", handle="official_agency", since_id=None)
    db.add(x_account)
    db.commit()
    return source, x_account


def _emit_tweet(db: Session, source: Source, x_account: XAccount, *, tweet_id: str, text: str) -> SourceItem:
    """Runs a real tweet through `XAdapter`'s fetch->normalize->validate->emit
    pipeline (mocked HTTP transport, no live network) exactly like the X2
    job does — not a hand-built `SourceItem`, so this exercises the rights
    gate and idempotent upsert for real."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"id": tweet_id, "text": text, "created_at": "2026-09-09T12:00:00.000Z"}], "meta": {"result_count": 1}},
        )

    adapter = XAdapter(source, x_account, "test-token")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    raw_items = adapter.fetch(client)
    assert len(raw_items.items) == 1
    normalized = adapter.normalize(raw_items.items[0])
    assert adapter.validate(normalized).valid
    return adapter.emit(db, normalized)


@requires_postgres
def test_disabled_x_account_story_never_reaches_published(migrated_database, monkeypatch):
    """Same test pattern as T08's non-X rights-gate test (NON_NEGOTIABLES
    #4/#12): a `DISABLED` X account's posts are blocked at emit() and never
    advance through clustering/generation/publish."""
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "true")
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source, x_account = _make_x_source(db, rights_status="DISABLED")
        item = _emit_tweet(db, source, x_account, tweet_id="900", text="Breaking: policy change announced today")

        assert item.ingest_status == "RIGHTS_BLOCKED"

        assert cluster_normalized_items(db) == 0
        assert generate_stories(db) == 0
        assert auto_publish_stories(db) == 0
        assert publish_due_stories(db) == 0
        assert db.scalars(select(Story)).first() is None


@requires_postgres
def test_sensitive_x_derived_story_never_auto_publishes(migrated_database, monkeypatch):
    """No official-account shortcut exists: an X-derived story classified
    IMMIGRATION/LEGAL/FINANCIAL/BREAKING must sit in REVIEW_REQUIRED like any
    other sensitive story, even with auto-publish globally enabled."""
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "true")
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source, x_account = _make_x_source(db)
        item = _emit_tweet(db, source, x_account, tweet_id="901", text="USCIS updates visa processing rules")
        assert item.ingest_status == "NORMALIZED"

        assert cluster_normalized_items(db) == 1
        db.refresh(item)
        assert item.ingest_status == "CLUSTERED"

        _use_fake_provider(monkeypatch, [_classification(sensitivity="IMMIGRATION"), _generation(sensitivity="IMMIGRATION")])
        assert generate_stories(db) == 1

        story = db.scalars(select(Story)).one()
        assert story.sensitivity == "IMMIGRATION"
        assert story.status == "REVIEW_REQUIRED"

        auto_publish_stories(db)
        db.refresh(story)
        assert story.status == "REVIEW_REQUIRED"
        assert story.status != "PUBLISHED"


@requires_postgres
def test_published_x_story_shows_canonical_attribution_to_account_and_post(migrated_database, monkeypatch):
    """The rendered story page's attribution must link to the specific post/
    account, not a generic 'X' label (§6.3.1)."""
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "true")
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source, x_account = _make_x_source(db)
        _emit_tweet(db, source, x_account, tweet_id="902", text="Official update: revised form instructions posted")

        assert cluster_normalized_items(db) == 1
        # The helper replays the list per call, so this classification payload
        # is also the stored draft: give it ADR-026-valid text.
        draft = {"headline_en": "Agency announces new policy", "summary_en": "A federal agency changed its rules. Applicants must follow them from next month."}
        _use_fake_provider(monkeypatch, [_classification(**draft), _generation()])
        assert generate_stories(db) == 1

        story = db.scalars(select(Story)).one()
        assert auto_publish_stories(db) == 1
        assert publish_due_stories(db) == 1
        db.refresh(story)
        assert story.status == "PUBLISHED"

        out = story_to_out(db, story)
        assert len(out.sources) == 1
        assert out.sources[0].url == "https://x.com/official_agency/status/902"
        assert out.sources[0].title == "Official Account"
        assert out.sources[0].is_x_post is True
        assert "revised form instructions" not in out.sources[0].title


@requires_postgres
def test_duplicate_x_post_fetch_never_creates_duplicate_rows(migrated_database):
    """A re-fetch of the same tweet (same external_id) upserts in place, and
    a repeated clustering sweep never creates a second `Story` for it."""
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source, x_account = _make_x_source(db)
        first = _emit_tweet(db, source, x_account, tweet_id="903", text="Agency announces new policy")
        second = _emit_tweet(db, source, x_account, tweet_id="903", text="Agency announces new policy")
        assert first.id == second.id
        assert db.scalars(select(SourceItem).where(SourceItem.source_id == source.id)).all() == [first]

        assert cluster_normalized_items(db) == 1
        assert cluster_normalized_items(db) == 0
        assert len(db.scalars(select(Story)).all()) == 1
        assert len(db.scalars(select(StorySource)).all()) == 1
