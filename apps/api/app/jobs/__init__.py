"""Postgres-backed job queue (§14, ADR-003). No Redis/Celery — see
NON_NEGOTIABLES #2. `queue.py` is the generic claim/complete/fail machinery;
one module per job `type` (starting with `source_fetch.py`, T08) implements
the actual work.
"""
