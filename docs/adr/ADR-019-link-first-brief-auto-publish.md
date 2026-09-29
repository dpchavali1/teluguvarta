# ADR-019: Auto-publish lane for link-first briefs

- **Status**: proposed
- **Date**: 2026-09-29
- **Ticket**: automation plan step 3 (`PROGRESS.md`); amends ADR-002 / NON_NEGOTIABLES #15, narrows ADR-011 for this lane only

## Context

Every story goes to a human today. `AUTO_PUBLISH_GLOBAL=false` in prod
(`infra/deploy/deploy.sh`), so `publish.auto_publish_stories` moves each
`AI_READY` story to `REVIEW_REQUIRED` with `AUTO_PUBLISH_DISABLED`. The owner is
the only reviewer. With ADR-018, AI drafts every story, so the queue fills
faster than one person can clear it.

Turning `AUTO_PUBLISH_GLOBAL` on is not acceptable either. It would publish full
AI summaries plus "why this matters" on ref-membership evidence alone. ADR-011
records this as an open gap: a claim can cite a real `SourceItem` without that
item saying what the claim says. Under ADR-002 (`LINK_ONLY`) the only evidence
stored is the source's `title`/`url`/`published_at`. For an AI summary,
nothing checks that its facts appear in the source.

The owner's plan: a narrow lane that publishes without review only when the
content is small enough to check deterministically against the source title.
This is a **link-first brief**: an original headline, one sentence limited to
what the source title says, and the source link as the main call to action.

Why this needs an ADR rather than a flag:

1. **It conflicts with NON_NEGOTIABLES #15 / ADR-002.** #15 says every published
   story is "an original AI-drafted summary + 'why this matters' + attribution +
   a link … never reproduced headline text". A brief leaves out "why this
   matters". Its one-liner also restates the source title's facts by design,
   which comes close to reproducing the headline.
2. **It settles ADR-011 for one content shape.** Whether ref-membership is
   enough is still undecided for full stories. This lane uses a stricter rule
   (title-match) for briefs only.
3. **Auto-publish is a product/editorial decision.** Per NON_NEGOTIABLES #11 it
   needs a recorded decision, not an implicit one.

## Decision (proposed; the owner decides the items marked **[Q]**)

### 1. What a brief is

- `headline_en`: an AI-drafted original headline. It must pass the existing
  similarity check against every source title in the cluster
  (`SUMMARY_SIMILARITY_FLAG_THRESHOLD`, applied to the headline too). A near-copy
  of the source headline fails, and the story goes to the normal review queue.
- `brief_en`: a single sentence of at most 30 words **[Q1: cap]**. It may only
  state facts in the source title(s). A deterministic check enforces this:
  - every number/date token in the sentence appears in a cited title;
  - every capitalized entity token (after stop-word removal) appears in a cited
    title;
  - no causal claim the title doesn't make: words like "because", "after",
    or "due to" are allowed only if the title contains them.
  A check failure is not auto-published. The story goes to review with reason
  `BRIEF_TITLE_MISMATCH`.
- Attribution plus the source link, shown as the main action ("Read at
  {source}").
- **No "why this matters"** **[Q2]**. This is the ADR-002 amendment: a brief is
  a permitted publish shape alongside the full story.
  NON_NEGOTIABLES #15 gets one sentence added: "…or, under ADR-019, a
  link-first brief (original headline + title-bounded sentence + attribution +
  link)."
- The brief is produced by a new gateway task (`generate_brief`, its own
  contract with `headline_en`, `brief_en`, `claims[]`). It goes through
  `packages/ai` like every AI call (NON_NEGOTIABLES #8). It is **only** tried
  after the normal generate pass has routed the story to review for
  `AUTO_PUBLISH_DISABLED`. Every other review reason keeps the story in review
  as it does today.

### 2. Eligibility (all must hold; any failure goes to the review queue as today)

- **Rights**: every item in the cluster comes from a source with
  `rights_status = LINK_ONLY` **and** a non-null `rights_reviewed_at` and
  `rights_evidence_url`. A source that is enabled but has no review record does
  not qualify.
- **Sensitivity**: `story.sensitivity = 'NONE'` from a classification that
  actually ran. Stories held as `NO_PAID_PROVIDER` were never classified, so
  they never qualify. In addition, the source's own `category` must not be
  immigration/legal/financial (the ADR-015 privacy categories), so a
  misclassification by the AI alone cannot open the lane. NON_NEGOTIABLES #5
  is unchanged: breaking (`urgency HIGH/URGENT`) is excluded.
- **Confidence**: classification and brief-generation confidence both at least
  0.8 **[Q3]**. The review threshold is 0.5, and this lane needs a higher bar.
- **Clean route**: the normal generate pass produced no other review reason (no
  `LOW_CONFIDENCE_*`, `SIMILARITY_TO_SOURCE`, `HIGH_IMPORTANCE`,
  `SENSITIVE_CATEGORY`).
- **Evidence**: every claim cites a real cluster item (the P0-1 check) and
  passes the title-match check in §1.

A single source is allowed. Because of the title-match check, outlet
corroboration (ADR-011's option 1b) is not needed for this shape.

### 3. Controls

- **Kill switch**: `AUTO_PUBLISH_BRIEFS` (default `false`). It is independent of
  `AUTO_PUBLISH_GLOBAL`, so the owner can open this lane without opening full
  auto-publish. The existing budget-breach gate (`AUTO_PUBLISH_DISABLE_ON_BUDGET_BREACH`)
  closes it too. The admin settings page shows its state next to the other flags.
- **Daily cap**: `AUTO_PUBLISH_BRIEFS_DAILY_CAP`, default 20 **[Q4: number]**.
  It counts `STORY_AUTO_APPROVED` audit events with
  `reason = BRIEF_LANE` since midnight **[Q5: UTC or America/New_York]**. Stories
  past the cap go to the review queue with reason `BRIEF_DAILY_CAP`, in the
  normal queue order. They are not held for the next day.
- **Audit**: every lane publish writes `AuditEvent(actor="system:brief_lane",
  action="STORY_AUTO_APPROVED", metadata={"reason": "BRIEF_LANE", "title_match": {...}})`.
  The metadata records which title tokens matched, so a reviewer can see why it
  passed.
- **After publish**: admin gets an "Auto-published briefs (24h)" list with the
  existing retract/correct actions. There is no pre-publish sampling: the cap
  plus the after-publish list is the review.

### 4. What stays the same

- Telugu: the brief is the canonical English variant. `ai_translate` and
  Telugu QA run as they do today (NON_NEGOTIABLES #7). The lane does not wait
  for Telugu, which matches the current publish behavior for English.
- `publish_due_stories`: unchanged. Lane stories go through
  `REVIEW_REQUIRED -> APPROVED -> SCHEDULED` like every auto-approved story, so
  the status trigger and audit trail are unchanged.
- Readers: a brief shows a "Brief" label, and its main action is the source
  link **[Q6: label wording, or no label]**. The label needs a story-format
  field (`story.format ∈ {FULL, BRIEF}`, migration, default `FULL`) and a small
  ADR-014 component variant. The component contract itself does not change.

## Consequences

- Plain factual stories from reviewed government/wire feeds (advisories,
  declarations, schedule notices) can go live without the owner, up to the cap.
  Everything else is reviewed as it is today.
- A published brief says less than a reviewed story. That is intended: the
  lane trades depth for checkability.
- **Remaining risk**: a title-bounded sentence can still mislead if it leaves out
  qualifiers the title contains. The token check catches added facts, not
  dropped ones. The cap and the after-publish list limit how far this can go.
- ADR-011 stays **proposed** for full stories. This ADR does not decide it.
- Depends on ADR-018 being live on the VPS. Without a paid route, eligible
  stories are held as `NO_PAID_PROVIDER` and never classified, so the lane
  stays empty.
- Step 4 of the plan (storing government RSS descriptions as evidence once they
  are rights-reviewed) would allow a later brief to check against the
  description as well as the title. That needs its own rights decision and is
  out of scope here.
- Revisit if retractions of lane stories exceed 2 in any 30-day window, or once
  a second reviewer exists.

## Alternatives considered

- **Turn on `AUTO_PUBLISH_GLOBAL`.** Rejected: it publishes full summaries plus
  "why this matters" on ref-membership only, which is the open ADR-011 gap.
- **Publish the source title verbatim with a link.** Rejected: ADR-002 / #15
  forbid reproducing headline text.
- **Bulk approve in admin.** Rejected earlier (2026-09-29 triage): it breaks the
  queue's "nothing decided unseen" rule.
- **Require two-outlet corroboration for the lane.** Rejected: most clusters
  have a single source, so the lane would be almost always empty. The
  title-match check gives the same protection for a brief.
