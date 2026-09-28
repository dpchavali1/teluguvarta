import httpx
import pytest

from app.ai.gateway import _resolve_provider
from app.ai.providers import gemini_provider
from app.ai.providers.base import ProviderUnavailableError
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.providers.null_provider import NullProvider
from app.ai.tasks import Task


def _patch_post(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        gemini_provider.httpx, "post",
        lambda url, **kw: httpx.Client(transport=transport).post(url, **kw),
    )


def test_missing_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("AI_GEMINI_API_KEY", raising=False)
    with pytest.raises(ProviderUnavailableError):
        GeminiProvider()
    assert isinstance(_resolve_provider("gemini"), NullProvider)


def test_complete_parses_json_and_usage(monkeypatch):
    monkeypatch.setenv("AI_GEMINI_API_KEY", "k")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers["x-goog-api-key"]
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": '{"a": 1}'}]}}],
            "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 3},
        })

    _patch_post(monkeypatch, handler)
    out = GeminiProvider().complete(model="gemini-3.8-flash", task=Task.SUMMARY, prompt="hi")
    assert out.output == {"a": 1} and (out.tokens_in, out.tokens_out) == (7, 3)
    assert seen["url"].endswith("/models/gemini-3.8-flash:generateContent")
    assert seen["key"] == "k"


def test_quota_error_is_unavailable(monkeypatch):
    monkeypatch.setenv("AI_GEMINI_API_KEY", "k")
    _patch_post(monkeypatch, lambda r: httpx.Response(429, json={}))
    with pytest.raises(ProviderUnavailableError):
        GeminiProvider().complete(model="m", task=Task.SUMMARY, prompt="hi")


def test_blocked_candidate_yields_empty_object(monkeypatch):
    monkeypatch.setenv("AI_GEMINI_API_KEY", "k")
    _patch_post(monkeypatch, lambda r: httpx.Response(200, json={"promptFeedback": {}}))
    out = GeminiProvider().complete(model="m", task=Task.SUMMARY, prompt="hi")
    assert out.output == {}


def test_gemini_is_not_in_default_routing():
    from app.ai.tasks import ROUTING
    assert all(
        "gemini" not in (r.provider, r.escalation_provider) for r in ROUTING.values()
    )
