"""P07 / ADR-041: student exam and deadline reminders (pure, no DB).

An editor enters each date by hand from an official page and links to it; a
second step approves it. There is no fetching, so no scraping or rights gate
is involved. `exam` is the editor's short key for an exam or programme."""

from __future__ import annotations

import re
from datetime import date

KINDS = ("REGISTRATION_DEADLINE", "EXAM_DATE", "RESULT_DATE", "APPLICATION_DEADLINE")
KIND_LABEL = {
    "REGISTRATION_DEADLINE": "registration deadline",
    "EXAM_DATE": "exam date",
    "RESULT_DATE": "result date",
    "APPLICATION_DEADLINE": "application deadline",
}
MAX_EXAM_FOLLOWS = 10
REMINDER_DAYS = (7, 1)
_EXAM_KEY = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,19}$")
_KEY_PREFIX = "exam_deadline:"


def normalize_exam(value: str) -> str | None:
    key = value.strip().upper()
    return key if _EXAM_KEY.match(key) else None


def https_url(url: str) -> bool:
    return url.lower().startswith("https://") and len(url) > len("https://") + 3


def entry_error(exam: str, kind: str, title: str, source_url: str) -> str | None:
    if normalize_exam(exam) is None:
        return "Exam key must be 2-20 characters: letters, digits or hyphen"
    if kind not in KINDS:
        return f"Unknown kind: {kind}"
    if not title.strip():
        return "Title is required"
    if not https_url(source_url):
        return "Source link must be an https page"
    return None


def notification_key(item_id: object, tag: str) -> str:
    return f"{_KEY_PREFIX}{item_id}:{tag}"


def parse_notification_key(key: str) -> tuple[str, str] | None:
    """(item id, tag) for an exam-deadline key, else None."""

    if not key.startswith(_KEY_PREFIX):
        return None
    item_id, _, tag = key.removeprefix(_KEY_PREFIX).partition(":")
    return (item_id, tag) if item_id and tag else None


def reminder_tag(deadline: date, today: date) -> str | None:
    days = (deadline - today).days
    return f"d{days}" if days in REMINDER_DAYS else None


def alert_copy(exam: str, kind: str, title: str, deadline: date, tag: str) -> tuple[str, str]:
    label = KIND_LABEL.get(kind, kind.lower())
    when = deadline.isoformat()
    if tag == "new":
        return f"{exam}: {label} added", f"{title} — {when}."
    days = tag.removeprefix("d")
    unit = "day" if days == "1" else "days"
    return f"{exam}: {label} in {days} {unit}", f"{title} — {when}."
