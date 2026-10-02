# T19 maintenance — typing and progress handoff

Owner explicitly requested this alongside UI15 on 2026-10-01. Depends on the
existing T19 implementation and current T13-repair/T14-search local work.

Reduce the API's existing 70 mypy errors with correct narrowing/typed schema
boundaries rather than increasing the CI allowance or disabling diagnostics.
Keep runtime behavior and public contracts. Run mypy, ruff and API tests;
lower `apps/api/mypy-baseline.txt` to the observed verified count.

Make `PROGRESS.md` a concise current handoff: active release/work statuses,
ordered next work, and latest verification. Move the existing full text
verbatim to a linked history file so no earlier implementation evidence is
lost. Preserve the build-order ticket status and outstanding gates.
