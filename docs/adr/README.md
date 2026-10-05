# Architecture Decision Records

Copy `TEMPLATE.md` to `ADR-0NN-short-title.md` when you hit a stop condition
in `docs/NON_NEGOTIABLES.md` or make a decision the spec leaves open.

## Required ADRs (per spec §23) — create when their trigger ticket is reached

| ADR | Topic | Trigger ticket | Status |
|---|---|---|---|
| ADR-001 | AI provider selection | T10 | **accepted** — see [ADR-001](ADR-001-ai-provider-selection.md) |
| ADR-002 | Source-rights approval policy | T06 | **accepted** — see [ADR-002](ADR-002-source-rights-approval-policy.md) |
| ADR-003 | Database job queue strategy | T08 | **accepted** — see [ADR-003](ADR-003-database-job-queue-strategy.md) |
| ADR-004 | Bilingual content lifecycle | T13 | **accepted** — see [ADR-004](ADR-004-bilingual-content-lifecycle.md) |
| ADR-005 | Personalization model | T16 | **accepted** — see [ADR-005](ADR-005-personalization-model.md) |
| ADR-006 | Account/privacy architecture | T05 | **proposed** — see [ADR-006](ADR-006-account-privacy-architecture.md) |
| ADR-007 | Production hosting/cost limits | T19 | **accepted** — see [ADR-007](ADR-007-production-hosting-cost-limits.md) |
| ADR-008 | Visual design refresh (no new UI framework) | T21 | **accepted** — see [ADR-008](ADR-008-visual-design-refresh.md) |
| ADR-009 | Single design-token source, generated per surface | T22 | **accepted** — see [ADR-009](ADR-009-single-token-source.md) |

Update the Status column when an ADR file is created, and again when it's
accepted. Add ad-hoc ADRs below this table as they're written.

## Ad-hoc ADRs

- ADR-002 above was written ahead of T06 per an explicit product decision
  to launch on `LINK_ONLY` sources only; see the ADR for context.
- ADR-010 | Folio visual redesign (superseded color/shape values by ADR-035) |
  ad hoc, user-requested | **accepted, historically** — see
  [ADR-010](ADR-010-folio-visual-redesign.md)
- ADR-011 | Claim evidence sufficiency for unattended publish | P0-1
  follow-up | **proposed** — see
  [ADR-011](ADR-011-claim-evidence-sufficiency.md)
- ADR-012 | First-login MFA enrollment flow | P0-3 | **accepted** — see
  [ADR-012](ADR-012-mfa-enrollment-flow.md)
- ADR-013 | Golden eval set trust tier (shrink to reviewed 30) | Spike 2 |
  **accepted** — see
  [ADR-013](ADR-013-golden-eval-set-trust-tier.md)
- ADR-014 | Editorial component contract for web/mobile/admin coherence |
  ad hoc, user-requested | **accepted** — see
  [ADR-014](ADR-014-editorial-component-contract.md)
- ADR-015 | Gemini free tier as an AI provider (amends ADR-001) | Phase −1 |
  **accepted** (2026-09-28) — see [ADR-015](ADR-015-gemini-free-tier.md)
- ADR-017 | Web "modern newsroom" redesign (web presentation only) |
  ad hoc, owner-requested | **accepted** — see
  [ADR-017](ADR-017-web-modern-newsroom-redesign.md) (ADR-016 is reserved
  by the Gemini/Hetzner plan)
- ADR-018 | Paid Gemini route so AI drafts every story (amends ADR-001,
  ADR-015) | automation plan step 2 | **accepted** (2026-09-29) — see
  [ADR-018](ADR-018-gemini-paid-route.md)
- ADR-019 | Auto-publish lane for link-first briefs (amends ADR-002 /
  NON_NEGOTIABLES #15; narrows ADR-011 for briefs only) | automation plan
  step 3 | **accepted and implemented** (2026-09-29) — see
  [ADR-019](ADR-019-link-first-brief-auto-publish.md)
- ADR-020 | Store public-domain government feed descriptions as internal
  evidence (amends ADR-002 / NON_NEGOTIABLES #15) | automation plan step 4 |
  **accepted and implemented** (2026-09-29) — see
  [ADR-020](ADR-020-government-description-evidence.md)
- ADR-021 | Free-tier quota accounting for pinned Gemini models (amends
  ADR-015 decision 6) | automation plan follow-up | **rejected** (2026-09-29, not needed)
  — see [ADR-021](ADR-021-free-tier-pinned-model-quota.md)
- ADR-022 | Public web on the VPS at theteluguedit.com (amends ADR-007) |
  web deploy | **accepted and implemented** (2026-09-29) — see
  [ADR-022](ADR-022-web-on-vps-theteluguedit.md)
- ADR-023 | What revoking a source's rights does to published, mixed-source
  and scheduled stories | review 2026-09-29 #7 | **proposed** (owner decision
  needed) — see [ADR-023](ADR-023-source-rights-revocation.md)
- ADR-024 | A total AI spend ceiling, not only a degradation threshold |
  review 2026-09-29 #2 | **proposed** (owner decision needed) — see
  [ADR-024](ADR-024-total-ai-spend-ceiling.md)
- ADR-025 | Recovering stories held by AI failures (audited manual retry) |
  review 2026-09-29 #1 | **accepted and implemented** (options 1 and 3, 2026-09-30) — see
  [ADR-025](ADR-025-held-story-recovery.md)
- ADR-026 | Minimum content for a published story, by format | review
  2026-09-29 #6 | **proposed** (owner decision needed) — see
  [ADR-026](ADR-026-publication-content-validation.md)
- ADR-027 | Story geography and importance, separated from publisher origin
  and model confidence | review 2026-09-29 #10 | **accepted** 2026-09-30 — see [ADR-027](ADR-027-story-geography-and-importance.md)
- ADR-028 | Admin session storage and revocation (HttpOnly cookie sessions
  vs. hardened bearer token, plus admin CSP) | review 2026-09-29 #15 |
  **accepted** (option A, 2026-09-30; review R11) — see
  [ADR-028](ADR-028-admin-session-storage.md)
- ADR-029 | Reader-report inbox: dedicated table/endpoint, lifecycle,
  retention, rate limits and editor-only access | review 2026-09-30 R6 |
  **accepted** 2026-09-30 as proposed — see
  [ADR-029](ADR-029-reader-report-inbox.md)
- ADR-030 | Reader navigation set mapped from topics, "Top stories" role,
  editorial coverage targets | review 2026-09-30 R8 | **proposed** (owner
  decision needed) — see
  [ADR-030](ADR-030-reader-navigation-and-coverage-targets.md)
- ADR-031 | Dashboard pause switches for AI and auto-publish; stale queue
  expiry | ops request 2026-10-01 | **accepted** — see
  [ADR-031](ADR-031-runtime-pause-switches-and-stale-queue.md)
- ADR-032 | Every stale review hold expires (extends ADR-031) | owner
  decision 2026-10-01 | **accepted** — see
  [ADR-032](ADR-032-every-stale-hold-expires.md)
- ADR-033 | Confirm server deletion before clearing local data; retain identity
  on failure for retry | UI11 | **accepted** (option A, owner 2026-10-01) — see
  [ADR-033](ADR-033-account-deletion-failure-recovery.md)
- ADR-034 | Audited withholding and optional bounded regeneration of existing
  Telugu variants | T13 / improvement item 3 | **accepted** (option A, owner
  2026-10-01) — see [ADR-034](ADR-034-audited-telugu-variant-repair.md)
- ADR-035 | Rounded controls and paired modern colors | UI15 |
  **accepted** (owner 2026-10-01) — see
  [ADR-035](ADR-035-rounded-modern-color-system.md)
- ADR-036 | Production deployment topology for T19 release proof |
  **proposed** (live target needed) — see
  [ADR-036](ADR-036-production-deployment-topology.md)
- ADR-037 | Reader presentation of official X updates | X5 |
  **proposed** (placement/account decision needed) — see
  [ADR-037](ADR-037-x-updates-reader-presentation.md)
- ADR-038 | Keep the release audit blocking on the unpatched Expo CLI
  advisory | T19 | **accepted** (owner 2026-10-02) — see
  [ADR-038](ADR-038-unpatched-expo-cli-advisory.md)
- ADR-039 | Firebase for mobile push and separately consented analytics
  (amends ADR-007) | T17-firebase | **accepted** (owner 2026-10-02) — see
  [ADR-039](ADR-039-firebase-mobile-push-and-analytics.md)
- ADR-042 | Sync saved story IDs and followed keywords for alerts (amends
  ADR-006, bounded) | P02 | **accepted** (owner 2026-10-03) — see
  [ADR-042](ADR-042-synced-saved-ids-and-keywords.md)
- ADR-045 | WhatsApp share card vs. ADR-002 (supersedes its Share Card deferral if A) | P08 | **accepted** (owner 2026-10-04, option A) — see
  [ADR-045](ADR-045-whatsapp-share-card.md)
- ADR-047 | Dated, owned exceptions for unpatched dev-tooling advisories (supersedes ADR-038 suppression ban) | T19 | **accepted** (owner 2026-10-04, option B; expiry date to confirm) — see
  [ADR-047](ADR-047-dated-audit-exceptions.md)
- ADR-051 | Mobile usage analytics default-on vs. ADR-039 / SPEC separate consent | — | **accepted** (owner 2026-10-04, option A) — see
  [ADR-051](ADR-051-mobile-analytics-default-on.md)
- ADR-052 | Breaking/high-importance review holds never expire + alert (amends ADR-032) | — | **proposed** (owner request 2026-10-04) — see
  [ADR-052](ADR-052-breaking-review-no-expiry-and-alert.md)
- ADR-053 | Coverage monitor with monitor-only reference headline feeds | — | **proposed** (owner request 2026-10-04) — see
  [ADR-053](ADR-053-coverage-monitor-reference-feeds.md)
