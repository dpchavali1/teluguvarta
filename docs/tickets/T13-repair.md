# T13 repair — existing Telugu variants (ADR-034 A)

Owner accepted option A on 2026-10-01. Depends on T13/ADR-004 and ADR-025.
Status: implemented locally; production deployment and reviewed-language
quality evidence remain separate. Verification is recorded in PROGRESS.

Implement current QA diagnostics in admin detail without read-time mutations.
ADMIN-only repair actions require a nonblank audit reason and expected English
and Telugu text hashes. Withhold sets FAILED and keeps text; repeated withholding
is harmless. Regenerate requires FAILED and the existing translatable story
statuses, deletes Telugu/resets translation work atomically, and shares ADR-025's
two manual-reset cap with exhausted-state retries. Serialize both paths and
English draft/correction writes on the story. Do not change English/publication,
review tasks, rights or existing sampling/privacy/budget/AI flags.

Guard translation completion against newer English/editor Telugu/work-state
changes and the reset audit history, including failures received after a reset
and resets that leave variant/work state absent. Use the normal sweep/gateway;
no new jobs, infrastructure, migrations or production repairs.

Admin UI: current issue codes versus stored QA, required reason, explicit
confirmation/cancel, busy/error/reload states, shared retries left, and notice
that cached copies refresh normally. Generated contracts must match API schemas.

Acceptance: real-Postgres API tests for RBAC, reasons, missing variants, audit,
English/search fallback, repeated/stale requests, cap/exhausted-reset sharing,
concurrent requests, paused/disabled AI, failed QA and stale in-flight outputs.
Scoped ruff/mypy, API suite; contracts generation/typecheck; admin lint/typecheck/
production build and fixture-browser confirmation/error/diagnostic journeys.
Tests never call real providers or change production. Update PROGRESS/plan and
record deployment/native-speaker quality acceptance as separate pending gates.
