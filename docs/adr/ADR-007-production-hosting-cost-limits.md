# ADR-007: Production hosting platform(s) and cost limits

- **Status**: accepted
- **Date**: 2026-09-09
- **Ticket**: T19

## Context

§10's technology table already fixes the *stack* (Next.js, Expo, FastAPI,
managed Postgres, Postgres jobs, no Redis/OpenSearch/Kubernetes) but leaves
open which managed platforms actually run it in production, and what the
concrete `MONTHLY_AI_BUDGET_USD` / `MONTHLY_INFRA_BUDGET_USD` /
`DAILY_AI_ALERT_USD` numbers in `.env.example` should be — every ticket
through T18 left those blank. T19 is the trigger ticket for this ADR per
`docs/NON_NEGOTIABLES.md`'s "Required ADRs" list, and launch cannot proceed
without real budget numbers for the auto-publish-disable-on-breach gate
(T19, `app/jobs/publish.py`) to actually mean anything.

Nothing here was measured against real production traffic (T19 was built
and load-tested only against a local single-instance Postgres — see
`PROGRESS.md`'s T19 entry). Every choice below is therefore an
*early-launch-phase* starting point sized for the traffic this product
realistically has at launch (§19: "keep the service free to users, minimize
operator spend"), not a scaled-traffic architecture decision — revisit once
real production traffic produces real numbers (there is no recruited-user
pilot to gate this on — see `PROGRESS.md`'s 2026-09-16 pilot-removal entry).

## Decision

**Hosting, one service per §10 layer, no new layer added**:

| Layer | Platform | Why this one |
|---|---|---|
| Web (`apps/web`) | Vercel | First-party Next.js SSR/ISR support (no custom Docker/edge config to maintain), built-in CDN + TLS, zero-effort preview deploys per PR |
| Admin (`apps/admin`) | Vercel (same account, second project) | Same reasoning as web; kept as a separate Vercel project (not a Next.js multi-zone) so a bad admin deploy can never take down the public site |
| API + worker (`apps/api`) | Render | Two services from one repo: a web service (FastAPI/uvicorn) and a background worker (the T08 job-poll loop, `app/jobs/worker.py::run_forever`) — Render's native "background worker" service type matches this job model exactly, with autoscale and zero-downtime deploys on the web service, no Kubernetes |
| Database | Supabase-managed Postgres | Named explicitly as spec-acceptable (§10); ships pg_trgm pre-enabled (NON_NEGOTIABLES #1), daily backups + point-in-time recovery included, and its `DATABASE_URL` is a drop-in for the existing SQLAlchemy/Alembic setup — no code changes from what T02–T19 already built against local Postgres |
| Object storage (future) | Cloudflare R2 | S3-compatible (no new client library beyond what an S3 SDK would need if images/exports ever ship), zero egress fees — relevant given §19's cost-minimization goal; unused today (no feature writes to object storage yet) |
| CDN/DNS | Cloudflare (DNS + proxy in front of Vercel/Render) | §10's named choice; also where `app/rate_limit.py`'s documented "process-local, would need a shared store if horizontally scaled" caveat gets a cheap answer later — Cloudflare rate-limiting rules at the edge, not a new backend dependency |
| Push | Expo push service (already integrated, T17) | No change — Expo already fans out to FCM/APNs |
| Mobile builds/store submission | Expo EAS Build + Submit | Standard pairing with the Expo SDK 57 app T15 already ships; avoids maintaining Xcode/Android Studio CI runners ourselves |
| Error tracking | Sentry (real account; `SENTRY_DSN` set) | T18 already speaks Sentry's HTTP protocol without the SDK — this ADR is only "turn a real DSN on in production," no new code |
| Analytics | PostHog Cloud (real account; `POSTHOG_API_KEY` set) | Same story as Sentry — T18's `app/analytics.py` already forwards to PostHog's HTTP API when configured |

**Cost limits** (`.env.example`, production values — early-launch phase, not
a scaled-traffic budget):

```
MONTHLY_AI_BUDGET_USD=150
DAILY_AI_ALERT_USD=10
MONTHLY_INFRA_BUDGET_USD=200
AUTO_PUBLISH_DISABLE_ON_BUDGET_BREACH=true
```

Rationale for each number:

- `MONTHLY_AI_BUDGET_USD=150` — sized for early-launch-scale story volume
  (not a public-scale launch): T10/T11's summary +
  classify + why-matters calls plus T13's translation call, at the cheapest
  viable model tier §19 already mandates, comfortably fit dozens of stories
  a day well under this. Breaching it auto-disables auto-publish (this
  ticket's `app/jobs/publish.py` change) rather than silently overspending.
- `DAILY_AI_ALERT_USD=10` — roughly 1/15th of the monthly figure, so a
  single bad day (a runaway retry loop, a provider price change) surfaces
  via `app/alerts.py::check_budget_alerts` well before it could burn a
  meaningful fraction of the monthly budget.
- `MONTHLY_INFRA_BUDGET_USD=200` — approximates Vercel (hobby/pro tier) +
  Render (one web + one worker, smallest paid tier) + Supabase (smallest
  paid tier, needed for reliable backups) + Cloudflare (free tier covers
  early-launch traffic) + Expo EAS (pay-per-build, sporadic) at that scale. This
  is a tracking/alerting number, not an enforced kill switch — infra spend
  isn't inside `AiGateway`'s control the way AI spend is, so there's
  nothing analogous to auto-disable; a breach is intended to prompt a human
  decision (e.g., which platform tier to bump), not automatic action.
- `AUTO_PUBLISH_DISABLE_ON_BUDGET_BREACH=true` — see this ticket's
  `app/jobs/publish.py` change: defaults to the safer behavior (fail toward
  more human review, not toward silently continuing to spend). An operator
  explicitly opts out, not in.

## Consequences

- Every platform above is "managed PaaS with autoscale," matching §10's
  "no Kubernetes / no microservice fleet" constraint — deploying is `git
  push` to each platform's connected repo, no infra-as-code layer to
  maintain for a single-region early launch.
- `app/rate_limit.py`'s in-process limiter (this ticket) is explicitly
  documented as needing a shared store once the API worker/web service is
  ever scaled to more than one instance on Render — Cloudflare's
  edge-level rate limiting (already in this ADR's stack) is the intended
  answer, not adding Redis.
- Nothing here is exercised against real traffic — the budget numbers, the
  platform choices, and the rate-limiter's single-instance assumption
  should all be revisited once real production traffic numbers exist. This ADR
  intentionally does not promise the reliability targets in §16
  (99.5% availability, P95 latency) are met on these platforms at scale —
  only that the local-Postgres, single-instance load test this ticket ran
  (documented in `PROGRESS.md`) met them at the traffic level tested.
- Backups: Supabase's included daily backups satisfy the mechanism; this
  ticket's `infra/scripts/backup.sh`/`restore.sh` (pg_dump/pg_restore,
  optional `age` encryption) is the vendor-independent fallback/monthly
  restore-test tool, verified once against local Postgres this same
  ticket — not yet run against a real Supabase project, since none exists
  in this sandbox.

## Alternatives considered

- **Fly.io instead of Render for the API/worker**: comparable fit (also
  supports a background-worker process type); Render was chosen for a
  simpler pricing model and native background-worker UI, not a
  correctness difference — either would satisfy §10.
- **A single VPS (e.g. one DigitalOcean droplet) running everything**:
  rejected — it would need self-managed TLS, backups, and process
  supervision that every platform above already provides, working against
  §19's "keep ops complexity low."
- **Self-hosting Postgres on the same VPS as the API**: rejected for the
  same reason, and specifically because it would give up Supabase's
  included point-in-time recovery, which this ticket's own restore-test
  requirement depends on being trustworthy.
- **Kubernetes on any managed provider (GKE/EKS/etc.)**: rejected outright
  per NON_NEGOTIABLES #3 ("modular monolith on managed infrastructure, no
  microservice fleet") — not proportionate to this product's scale.
