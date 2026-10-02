"""ADR-034 repair transactions, shared caps and in-flight output races."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.contracts import TranslationResult
from app.ai.gateway import GatewayOutcome, GatewayStatus
from app.jobs import ai_retry, translate
from app.models import AiWorkState, AuditEvent, Job, ReviewTask, Story, StoryVariant
from app.switches import set_switch
from tests.conftest import requires_postgres
from tests.test_editorial_workflow import (
    _auth,
    _make_review_required_story,
    _publish,
    _token,
)

pytestmark = requires_postgres


def _setup(db, *, qa="PASSED", published=False, sensitivity="NONE"):
    story = _make_review_required_story(db, sensitivity=sensitivity)
    if published:
        _publish(db, story)
    te = StoryVariant(story_id=story.id, language="te", headline="తెలుగు ಸುದ್ದಿ",
                      summary="వార్త వివరాలు విద్యార్థులకు అందుబాటులో ఉన్నాయి.",
                      why_matters="వార్త పాఠకులకు ఉపయోగపడుతుంది.", qa_status=qa)
    db.add(te)
    db.commit()
    return story


def _payload(client, token, story, action="withhold"):
    info = client.get(f"/v1/admin/stories/{story.id}", headers=_auth(token)).json()["telugu_repair"]
    return {"action": action, "reason": "Wrong script confirmed by editor",
            "english_text_hash": info["english_text_hash"], "telugu_text_hash": info["telugu_text_hash"]}


def _repair(client, token, story, payload):
    return client.post(f"/v1/admin/stories/{story.id}/repair-telugu", headers=_auth(token), json=payload)


def _te(db, story):
    db.expire_all()
    return db.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "te")).first()


def _events(db, story, action):
    return db.scalars(select(AuditEvent).where(AuditEvent.entity_id == story.id, AuditEvent.action == action)).all()


def test_diagnostics_do_not_mutate_passed_variants(client, db_session):
    token = _token(client, db_session)
    story = _setup(db_session)
    detail = client.get(f"/v1/admin/stories/{story.id}", headers=_auth(token)).json()
    assert "MIXED_SCRIPT:headline" in detail["telugu_repair"]["qa_issues"]
    assert detail["variants"]["te"]["qa_status"] == "PASSED"
    assert detail["telugu_repair"]["resets_left"] == 2
    assert not detail["telugu_repair"]["can_regenerate"]
    assert _te(db_session, story).qa_status == "PASSED"
    assert not _events(db_session, story, "TELUGU_VARIANT_WITHHELD")


def test_withhold_is_audited_idempotent_and_public_search_falls_back(client, db_session):
    token = _token(client, db_session)
    story = _setup(db_session, published=True)
    before = client.get(f"/v1/admin/stories/{story.id}", headers=_auth(token)).json()
    payload = _payload(client, token, story)
    assert _repair(client, token, story, payload).status_code == 200
    assert _repair(client, token, story, payload).status_code == 200
    after = client.get(f"/v1/admin/stories/{story.id}", headers=_auth(token)).json()
    for field in ["status", "published_at", "review_task", "corrections"]:
        assert before[field] == after[field]
    assert before["variants"]["en"] == after["variants"]["en"]
    assert _te(db_session, story).headline == before["variants"]["te"]["headline"]
    assert _te(db_session, story).qa_status == "FAILED"
    event, = _events(db_session, story, "TELUGU_VARIANT_WITHHELD")
    assert event.actor == "admin@example.com"
    assert event.metadata_["previous_qa_status"] == "PASSED"
    assert event.metadata_["new_qa_status"] == "FAILED"
    assert event.metadata_["telugu_text_hash"] == payload["telugu_text_hash"]
    assert "MIXED_SCRIPT:headline" in event.metadata_["qa_issues"]
    assert not _events(db_session, story, "AI_RETRY_RESET")
    assert "te" not in client.get(f"/v1/stories/{story.canonical_slug}").json()["variants"]
    assert client.get("/v1/search", params={"q": "ಸುದ್ದಿ"}).json()["items"] == []
    assert client.get("/v1/search", params={"q": "Old headline"}).json()["items"]


def test_regeneration_requires_withholding_and_atomically_resets_work(client, db_session):
    token = _token(client, db_session)
    story = _setup(db_session)
    payload = _payload(client, token, story, "regenerate")
    assert _repair(client, token, story, payload).status_code == 409
    assert _repair(client, token, story, {**payload, "action": "withhold"}).status_code == 200
    db_session.add(AiWorkState(story_id=story.id, stage="TRANSLATE", input_version="old", failure_class="EXHAUSTED"))
    db_session.commit()
    assert _repair(client, token, story, payload).status_code == 200
    assert _te(db_session, story) is None
    assert db_session.scalars(select(AiWorkState).where(AiWorkState.story_id == story.id)).first() is None
    assert db_session.get(Story, story.id).status == "REVIEW_REQUIRED"
    assert db_session.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).one().status == "PENDING"
    event, = _events(db_session, story, "AI_RETRY_RESET")
    assert event.metadata_["stage"] == "TRANSLATE"
    assert event.metadata_["origin"] == "telugu_repair"
    assert event.metadata_["reset_number"] == 1
    assert _repair(client, token, story, payload).status_code == 409


@pytest.mark.parametrize("invalid", ["reason", "stale", "missing_en", "missing_te"])
def test_invalid_repair_has_no_side_effects(client, db_session, invalid):
    token = _token(client, db_session)
    story = _setup(db_session)
    payload = _payload(client, token, story)
    if invalid == "reason": payload["reason"] = "   "
    if invalid == "stale": payload["english_text_hash"] = "0" * 64
    if invalid in ("missing_en", "missing_te"):
        variant = db_session.scalars(select(StoryVariant).where(
            StoryVariant.story_id == story.id, StoryVariant.language == ("en" if invalid == "missing_en" else "te"),
        )).one()
        db_session.delete(variant)
        db_session.commit()
    response = _repair(client, token, story, payload)
    assert response.status_code == (422 if invalid == "reason" else 409)
    assert not _events(db_session, story, "TELUGU_VARIANT_WITHHELD")
    assert not _events(db_session, story, "AI_RETRY_RESET")


def test_only_admin_can_repair(client, db_session):
    token = _token(client, db_session, role="EDITOR")
    story = _setup(db_session)
    payload = _payload(client, token, story)
    assert _repair(client, token, story, payload).status_code == 403
    assert client.post(f"/v1/admin/stories/{story.id}/repair-telugu", json=payload).status_code == 401


def test_cap_is_shared_with_existing_exhausted_retries(client, db_session):
    token = _token(client, db_session)
    story = _setup(db_session, qa="FAILED")
    db_session.add(AiWorkState(story_id=story.id, stage="TRANSLATE", input_version="v", failure_class="EXHAUSTED"))
    db_session.commit()
    assert client.post(f"/v1/admin/stories/{story.id}/retry-ai", json={"stage": "TRANSLATE", "reason": "outage fixed"}, headers=_auth(token)).status_code == 200
    assert _repair(client, token, story, _payload(client, token, story, "regenerate")).status_code == 200
    db_session.add(StoryVariant(story_id=story.id, language="te", headline="తెలుగు", summary="వార్త వివరాలు", qa_status="FAILED"))
    state = AiWorkState(story_id=story.id, stage="TRANSLATE", input_version="new", failure_class="EXHAUSTED")
    db_session.add(state)
    db_session.commit()
    assert _repair(client, token, story, _payload(client, token, story, "regenerate")).status_code == 409
    assert _te(db_session, story) is not None
    assert db_session.get(AiWorkState, state.id) is not None
    assert len(_events(db_session, story, "AI_RETRY_RESET")) == 2


@pytest.mark.parametrize("mixed_paths", [False, True])
def test_concurrent_resets_cannot_exceed_cap(client, db_session, mixed_paths):
    token = _token(client, db_session)
    story = _setup(db_session, qa="FAILED")
    db_session.add(AuditEvent(actor="earlier", action="AI_RETRY_RESET", entity_type="story", entity_id=story.id, metadata_={"stage": "TRANSLATE"}))
    db_session.add(AiWorkState(story_id=story.id, stage="TRANSLATE", input_version="v", failure_class="EXHAUSTED"))
    db_session.commit()
    payload = _payload(client, token, story, "regenerate")
    barrier = Barrier(2)
    def request(index):
        barrier.wait(timeout=10)
        if mixed_paths and index == 1:
            return client.post(f"/v1/admin/stories/{story.id}/retry-ai", json={"stage": "TRANSLATE", "reason": "retry"}, headers=_auth(token)).status_code
        return _repair(client, token, story, payload).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(request, index) for index in range(2)]
        assert sorted(future.result(timeout=15) for future in futures) == [200, 409]
    assert len(_events(db_session, story, "AI_RETRY_RESET")) == 2


def _outcome():
    return GatewayOutcome(status=GatewayStatus.OK, result=TranslationResult(
        headline_te="తెలుగు వార్త", summary_te="వార్త వివరాలు పాఠకులకు అందుబాటులో ఉన్నాయి.",
        why_matters_te="వార్త పాఠకులకు ఉపయోగపడుతుంది.",
    ))


@pytest.mark.parametrize("change", ["english", "editor_te", "state_reset", "reset_without_state", "stale_failure"])
def test_inflight_output_cannot_restore_stale_text_or_state(db_session, monkeypatch, change):
    story = _make_review_required_story(db_session)
    story_id = story.id
    en = db_session.scalars(select(StoryVariant).where(StoryVariant.story_id == story_id)).one()
    version = ai_retry.input_version([en.headline, en.summary, en.why_matters])
    if change in ("state_reset", "stale_failure"):
        db_session.add(AiWorkState(story_id=story_id, stage="TRANSLATE", input_version=version))
        db_session.commit()
    def complete(*args, **kwargs):
        with Session(db_session.bind) as other:
            other.scalars(select(Story).where(Story.id == story_id).with_for_update()).one()
            if change == "english":
                current = other.get(StoryVariant, en.id)
                current.headline = "Corrected English"
            elif change == "editor_te":
                other.add(StoryVariant(story_id=story_id, language="te", headline="కొత్త తెలుగు", summary="కొత్త వార్త వివరాలు", qa_status="PASSED"))
            elif change == "reset_without_state":
                # A newly requested repair can leave both variant and retry state
                # absent, just as they were before this older call started.
                other.add(AuditEvent(actor="administrator", action="AI_RETRY_RESET", entity_type="story", entity_id=story_id,
                                     metadata_={"stage": "TRANSLATE", "origin": "telugu_repair"}))
            else:
                state = other.scalars(select(AiWorkState).where(AiWorkState.story_id == story_id)).one()
                other.delete(state)
            other.commit()
        return GatewayOutcome(status=GatewayStatus.HOLD) if change == "stale_failure" else _outcome()
    monkeypatch.setattr(translate.AiGateway, "run_task", complete)
    assert translate.translate_stories(db_session) == 1
    te = _te(db_session, story)
    assert (te.headline == "కొత్త తెలుగు") if change == "editor_te" else te is None
    if change in ("state_reset", "stale_failure"):
        assert db_session.scalars(select(AiWorkState).where(AiWorkState.story_id == story_id)).first() is None


def test_regeneration_remains_missing_when_translation_disabled(client, db_session, monkeypatch):
    token = _token(client, db_session)
    story = _setup(db_session, qa="FAILED")
    assert _repair(client, token, story, _payload(client, token, story, "regenerate")).status_code == 200
    monkeypatch.setenv("AI_TRANSLATION_ENABLED", "false")
    monkeypatch.setattr(translate.AiGateway, "run_task", lambda *args, **kwargs: pytest.fail("disabled translation called gateway"))
    translate.run_ai_translate(db_session, Job())
    assert _te(db_session, story) is None


def test_regeneration_uses_normal_qa_and_fallback(client, db_session, monkeypatch):
    token = _token(client, db_session)
    story = _setup(db_session, qa="FAILED")
    assert _repair(client, token, story, _payload(client, token, story, "regenerate")).status_code == 200
    monkeypatch.setattr(translate.AiGateway, "run_task", lambda *args, **kwargs: GatewayOutcome(
        status=GatewayStatus.OK, result=TranslationResult(headline_te="Wrong script", summary_te="English only")))
    translate.translate_stories(db_session)
    assert _te(db_session, story).qa_status == "FAILED"


def test_semantic_concern_can_be_withheld_without_automated_issues(client, db_session):
    token = _token(client, db_session)
    story = _setup(db_session)
    _te(db_session, story).headline = "తెలుగు వార్త"
    db_session.commit()
    info = client.get(f"/v1/admin/stories/{story.id}", headers=_auth(token)).json()["telugu_repair"]
    assert info["qa_issues"] == []
    assert _repair(client, token, story, _payload(client, token, story)).status_code == 200
    assert _te(db_session, story).qa_status == "FAILED"


def test_archived_story_cannot_regenerate(client, db_session):
    token = _token(client, db_session)
    story = _setup(db_session, qa="FAILED")
    story.status = "ARCHIVED"
    db_session.commit()
    assert _repair(client, token, story, _payload(client, token, story, "regenerate")).status_code == 409
    assert _te(db_session, story) is not None
    assert not _events(db_session, story, "AI_RETRY_RESET")


def test_paused_ai_defers_regeneration_without_provider_call(client, db_session, monkeypatch):
    from app.ai import gateway
    token = _token(client, db_session)
    story = _setup(db_session, qa="FAILED")
    assert _repair(client, token, story, _payload(client, token, story, "regenerate")).status_code == 200
    set_switch(db_session, "ai", False, "admin@example.com", "test pause")
    db_session.commit()
    monkeypatch.setattr(gateway, "_resolve_provider", lambda *args: pytest.fail("paused AI reached provider"))
    translate.translate_stories(db_session)
    assert _te(db_session, story) is None
    state = db_session.scalars(select(AiWorkState).where(AiWorkState.story_id == story.id)).one()
    assert state.last_status == "DEFERRED"


def test_successful_regeneration_preserves_sensitive_sampling_and_review(client, db_session, monkeypatch):
    token = _token(client, db_session)
    story = _setup(db_session, qa="FAILED", sensitivity="LEGAL")
    assert _repair(client, token, story, _payload(client, token, story, "regenerate")).status_code == 200
    def complete(*args, **kwargs):
        assert kwargs["privacy_decision"].value == "RESTRICTED"
        return _outcome()
    monkeypatch.setattr(translate.AiGateway, "run_task", complete)
    monkeypatch.setenv("TELUGU_REVIEW_SAMPLE_RATE", "1")
    translate.translate_stories(db_session)
    assert _te(db_session, story).qa_status == "PASSED"
    assert db_session.get(Story, story.id).status == "REVIEW_REQUIRED"
    tasks = db_session.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).all()
    assert len(tasks) == 2
    assert all(task.status == "PENDING" for task in tasks)
