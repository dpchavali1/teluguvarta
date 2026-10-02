# ADR-037: Reader presentation of official X updates

- **Status**: proposed — reader placement and account allowlist pending
- **Date**: 2026-10-01
- **Ticket**: X5

## Context

X1–X4 fetch curated official-account posts through the official X API and
send them through the normal rights, dedupe, AI and editorial pipeline. The
owner wants current visa-related X updates visible in the app with details
and a link to the original post. The current spec makes X a discovery signal,
not a license to reproduce posts; `LINK_ONLY` is the only enabled rights tier
(ADR-002), and immigration stories always require human approval. An
unreviewed live X timeline or copied post text would conflict with those
rules. The app already has five bottom tabs, so adding an X tab changes its
information architecture.

## Decision needed

Choose whether published X-derived stories appear in the existing news feed
with a clear official-source label and optional filter, or in a separately
named Official Updates section. In either placement, cards and details show
our original English/Telugu story, the reviewed source name, publication
date and a link to the specific X post. They never show raw post text, images
or an unreviewed live timeline. Source accounts start `DISABLED`; an ADMIN
must verify stable X user ID, official ownership, rights evidence, API access
and budget before enabling. Every visa/immigration story remains in human
review. No X credentials are sent to mobile clients and no scraping fallback
is permitted.

Candidate accounts for review may include the State Department Bureau of
Consular Affairs' `@TravelGov`, which
[`travel.state.gov`](https://travel.state.gov/en/international-travel/planning/guidance/travel-industry.html)
identifies as official.
Candidates are not automatically approved, enabled or assumed to post only
visa material. The admin must record account-specific evidence and curate
scope before polling.

## Consequences

The existing pipeline and moderation policy remain intact, while readers gain
clear X attribution. A separate section adds navigation and empty-state work;
an existing-feed filter is smaller and avoids a sixth tab. API access and
source approvals are needed for real posts to appear.

## Alternatives considered

- Embed or mirror raw posts: rejected under ADR-002's `LINK_ONLY` policy and
  the rule that X content is a source signal.
- Scrape public X pages if API access is missing: prohibited by the spec.
