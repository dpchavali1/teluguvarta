from datetime import UTC, datetime

from app.ai.budget import quota_day_start


def test_quota_day_starts_at_pacific_midnight_in_summer():
    # 03:00 UTC on Sep 28 is still Sep 27 evening in Pacific (PDT, UTC-7).
    assert quota_day_start(datetime(2026, 9, 28, 3, tzinfo=UTC)) == datetime(2026, 9, 27, 7, tzinfo=UTC)
    assert quota_day_start(datetime(2026, 9, 28, 8, tzinfo=UTC)) == datetime(2026, 9, 28, 7, tzinfo=UTC)


def test_quota_day_starts_at_pacific_midnight_in_winter():
    # PST is UTC-8.
    assert quota_day_start(datetime(2026, 12, 1, 9, tzinfo=UTC)) == datetime(2026, 12, 1, 8, tzinfo=UTC)


def test_quota_day_handles_dst_transition_day():
    # US spring-forward 2026-03-08: that Pacific day starts at 08:00 UTC (PST)
    # even though it ends at 07:00 UTC next day (PDT) — a 23h day.
    assert quota_day_start(datetime(2026, 3, 8, 20, tzinfo=UTC)) == datetime(2026, 3, 8, 8, tzinfo=UTC)
