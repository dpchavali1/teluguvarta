"""Structured (JSON) logging shared by the API request path and the worker
(T18). A single `contextvars`-backed context carries request_id/actor/
job_type/story_id so every log line emitted while handling a request or
running a job carries them automatically, without threading them through
every function signature.

`configure_logging()` is called once, from `app.main` and
`app.jobs.worker`, to install the JSON formatter on the root logger. Call
sites get a logger via `get_logger(__name__)` and log normally
(`logger.info("thing happened")`) — the formatter reads the current
context at emit time.
"""

from __future__ import annotations

import json
import logging
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_actor: ContextVar[str | None] = ContextVar("actor", default=None)
_job_type: ContextVar[str | None] = ContextVar("job_type", default=None)
_job_id: ContextVar[str | None] = ContextVar("job_id", default=None)
_story_id: ContextVar[str | None] = ContextVar("story_id", default=None)

_CONTEXT_VARS: dict[str, ContextVar[str | None]] = {
    "request_id": _request_id,
    "actor": _actor,
    "job_type": _job_type,
    "job_id": _job_id,
    "story_id": _story_id,
}


def current_context() -> dict[str, str]:
    """The subset of context fields currently set, for attaching to log
    lines, Sentry-equivalent error reports, and alert messages alike."""
    return {name: value for name, var in _CONTEXT_VARS.items() if (value := var.get()) is not None}


@contextmanager
def request_context(request_id: str, actor: str | None = None):
    tokens = [_request_id.set(request_id)]
    if actor is not None:
        tokens.append(_actor.set(actor))
    try:
        yield
    finally:
        for token in tokens:
            token.var.reset(token)


def set_actor(actor: str) -> None:
    """Called from `app.auth`'s dependencies once a principal is resolved,
    so the rest of the request (including an unhandled-exception capture)
    can see who was making the call — the request-id middleware runs before
    auth, so it can't know this itself."""
    _actor.set(actor)


@contextmanager
def job_context(job_type: str, job_id: str | UUID | None = None, story_id: str | UUID | None = None):
    tokens = [_job_type.set(job_type)]
    if job_id is not None:
        tokens.append(_job_id.set(str(job_id)))
    if story_id is not None:
        tokens.append(_story_id.set(str(story_id)))
    try:
        yield
    finally:
        for token in tokens:
            token.var.reset(token)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **current_context(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
