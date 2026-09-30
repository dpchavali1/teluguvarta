# apps/api — FastAPI backend. See docs/tickets/T01.md, T03.md, T04.md.

Runtime dependencies are pinned with hashes in `requirements.lock`, which the
image installs (`infra/deploy/api.Dockerfile`). After changing `dependencies`
in `pyproject.toml`, rerun the command in the lock's header and commit both;
CI fails on a stale lock. `mypy-baseline.txt` holds the current mypy error
count: CI fails if `mypy app` reports more, so lower it when you fix some.
