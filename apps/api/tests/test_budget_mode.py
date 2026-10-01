"""Review 2026-09-30 R4: admin's budget mode must say what the gateway's
gates actually do at a given spend."""

from datetime import UTC, datetime

import pytest

from app.ai import budget
from app.ai.budget import budget_mode, reporting_windows


@pytest.fixture
def thresholds(monkeypatch):
    monkeypatch.setenv("MONTHLY_AI_BUDGET_USD", "50")
    monkeypatch.setenv("MONTHLY_AI_HARD_CAP_USD", "60")


@pytest.mark.parametrize(
    ("spend", "mode"),
    [(0.0, "NORMAL"), (49.99, "NORMAL"), (50.0, "CLASSIFICATION_ONLY"), (59.99, "CLASSIFICATION_ONLY"),
     (60.0, "PAID_STOPPED"), (75.0, "PAID_STOPPED")],
)
def test_mode_matches_gateway_gates(thresholds, monkeypatch, spend, mode):
    monkeypatch.setattr(budget, "month_to_date_cost_usd", lambda db, now=None: spend)
    assert budget_mode(spend) == mode
    # The gateway stops degradable tasks on is_over_monthly_budget and paid
    # calls on is_over_hard_cap; the mode must agree with both.
    assert budget.is_over_monthly_budget(None) == (mode != "NORMAL")
    assert budget.is_over_hard_cap(None) == (mode == "PAID_STOPPED")


def test_mode_is_normal_without_thresholds(monkeypatch):
    monkeypatch.delenv("MONTHLY_AI_BUDGET_USD", raising=False)
    monkeypatch.delenv("MONTHLY_AI_HARD_CAP_USD", raising=False)
    assert budget_mode(1000.0) == "NORMAL"


def test_reporting_windows_are_utc_and_quota_resets_at_pacific_midnight():
    windows = reporting_windows(datetime(2026, 9, 30, 23, 35, tzinfo=UTC))
    assert windows["day_start"] == datetime(2026, 9, 30, tzinfo=UTC)
    assert windows["month_start"] == datetime(2026, 9, 1, tzinfo=UTC)
    # 23:35 UTC is 16:35 PDT; the next Pacific midnight is 07:00 UTC.
    assert windows["quota_resets_at"] == datetime(2026, 10, 1, 7, tzinfo=UTC)


def test_quota_reset_crosses_dst_at_midnight():
    # 2026-11-01 is the US fall-back day: midnight Pacific on Nov 2 is PST (UTC-8).
    windows = reporting_windows(datetime(2026, 11, 1, 12, tzinfo=UTC))
    assert windows["quota_resets_at"] == datetime(2026, 11, 2, 8, tzinfo=UTC)
