# ADR-036: Confirm the production deployment topology

- **Status**: proposed — awaiting the live host/project identity
- **Date**: 2026-10-01
- **Ticket**: T19 release and recovery proof

## Context

Accepted ADR-007 chooses Vercel for web/admin, Render for API/worker, and
Supabase Postgres. The later `infra/deploy/` runbooks and production Compose
stack instead operate all services and Postgres on one VPS. Both cannot be the
current release/restore procedure. The owner has asked for deployment and
recovery proof, so guessing which topology is live would risk running a
destructive procedure against the wrong environment. `PROGRESS.md` has no
production deployment evidence, and this checkout has no `.env.prod`.

## Decision needed

Confirm the live host/project and access method. If the VPS is the accepted
deployment, supersede ADR-007's platform row and record the VPS backup,
offsite-storage and availability tradeoffs. If the managed platforms are live,
use their migrations, backups, restore and rollback procedures and retire the
VPS runbook as production authority. In either case, record the deployed
revision, migration head, health/MFA/logout and recovery evidence without
secrets before marking T19's release gate complete.

Until then, production deploy, restore drill, alert injection and rollback
remain unverified. Local shell checks and simulated restore tests can proceed.

## Consequences

One unambiguous runbook and evidence trail will govern releases. The current
repository is not enough to claim production proof.

## Alternatives considered

- Assume the VPS scripts are live because they exist: rejected because
  ADR-007 remains accepted and no host identity or credentials are recorded.
- Assume the managed stack is live because ADR-007 is accepted: rejected
  because the later VPS deployment tooling and review mention a single VPS.
