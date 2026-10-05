"""ADR-031: dashboard pause switches.

Two switches an ADMIN flips from the dashboard, read on every worker loop so
a flip takes effect within one poll, no restart:

- `ai`: off -> no AI provider is called (worker stops claiming AI jobs, the
  gateway answers DEFERRED as a backstop).
- `auto_publish`: off -> nothing publishes automatically; stories wait in
  AI_READY. Hand-approved stories still publish.

- `breaking` (ADR-054): off -> breaking/death stories stay in review. The env
  flag `AUTO_PUBLISH_BREAKING` defaults off.

A missing row means on. Env flags stay a hard ceiling: the effective state is
"env allows it AND the switch is on", so `AUTO_PUBLISH_GLOBAL=false` keeps
auto-publish off whatever the dashboard says.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.orm import Session

from app.models import RuntimeSwitch

SwitchKey = Literal["ai", "auto_publish", "breaking"]
SWITCH_KEYS: tuple[SwitchKey, ...] = ("ai", "auto_publish", "breaking")

AUTO_PUBLISH_GLOBAL_ENV = "AUTO_PUBLISH_GLOBAL"
AUTO_PUBLISH_BREAKING_ENV = "AUTO_PUBLISH_BREAKING"


def env_allows(key: SwitchKey) -> bool:
    """The server-side ceiling. AI has none beyond ADR-024's budget caps."""
    if key == "auto_publish":
        return os.environ.get(AUTO_PUBLISH_GLOBAL_ENV, "false").lower() == "true"
    if key == "breaking":
        return os.environ.get(AUTO_PUBLISH_BREAKING_ENV, "false").lower() == "true"
    return True


def switch_row(db: Session, key: SwitchKey) -> RuntimeSwitch | None:
    return db.get(RuntimeSwitch, key)


def dashboard_on(db: Session, key: SwitchKey) -> bool:
    row = switch_row(db, key)
    return True if row is None else row.enabled


def is_on(db: Session, key: SwitchKey) -> bool:
    return env_allows(key) and dashboard_on(db, key)


def ai_paused(db: Session) -> bool:
    return not dashboard_on(db, "ai")


def auto_publish_paused(db: Session) -> bool:
    """Paused from the dashboard specifically (env off is a different mode:
    everything goes to the review queue)."""
    return not dashboard_on(db, "auto_publish")


def set_switch(db: Session, key: SwitchKey, enabled: bool, actor: str, note: str | None) -> RuntimeSwitch:
    row = switch_row(db, key)
    if row is None:
        row = RuntimeSwitch(key=key, enabled=enabled, updated_by=actor, note=note)
        db.add(row)
    else:
        row.enabled = enabled
        row.updated_by = actor
        row.note = note
    row.updated_at = datetime.now(UTC)
    db.flush()
    return row
