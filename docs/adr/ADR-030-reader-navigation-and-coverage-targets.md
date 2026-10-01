# ADR-030: Reader navigation set, "Top stories" role and editorial coverage targets

- **Status**: proposed (owner decision needed)
- **Date**: 2026-09-30
- **Ticket**: review 2026-09-30 R8 (`docs/reviews/2026-09-30-live-product-and-admin-plan.md`)

## Context

The live review found published coverage concentrated: 15 of 17 stories in
the snapshot came from one publisher. Politics and overlapping
regional/local/state categories dominated navigation, and no immigration or
student story appeared. R8 asks for three things that are product decisions,
not engineering ones:

1. **Topic sprawl.** The classifier returns free-text `categories`
   (`app/ai/contracts.py`), and `generate._link_topics` creates a new `Topic`
   row for any slug it hasn't seen before. Nothing limits that vocabulary.
   The web header lists every active topic that has a story
   (`apps/web/src/app/layout.tsx::navTopics`), so each new label the model
   invents becomes a navigation item. The local dev database already has 26
   active topics.
2. **"Top stories" has no defined meaning.** On the web home page
   (`HomeFeed.tsx`), the "Top stories" rail is items 2–5 of the feed. For a
   reader with no preferences that feed is ordered by recency. An editor
   doesn't choose them, and since ADR-027 there is a real `importance`
   signal, but the rail doesn't use it.
3. **No coverage targets.** Enabled feeds don't guarantee useful published
   coverage. The SPEC names NRI and student readers as first-class, but
   nothing checks whether either audience got any stories this week.

The new admin **Coverage** page (`GET /v1/admin/coverage`, R8) measures all
three: feed yield by outcome, share by publisher, topics with nothing
published, and time to publish. It doesn't decide anything. Choosing a
taxonomy, defining what makes a story "top", or setting targets changes what
readers see. CLAUDE.md says not to invent requirements, so this ADR asks for
the owner's decision.

## Decision (proposed; each part can be accepted separately)

**A. A fixed reader navigation set, mapped from existing topics.** Readers see
a short, ordered list, for example: Andhra Pradesh, Telangana, India, US
immigration, Students, Cinema, Business, Sports. Each item maps to one or
more existing topic slugs. The mapping is data (a new `nav_sections` table
or config), not renamed topics, so:
- existing `/topics/{slug}` URLs, saved user topics and alert subscriptions
  keep working unchanged;
- classifier topics that aren't mapped stay in the database and in admin
  filters, but leave reader navigation;
- `_link_topics` keeps creating topics (no AI contract change). The
  Coverage page shows unmapped topics that received stories, so an editor
  can map them.

The owner supplies the section list and the slug mapping. Engineering doesn't
guess it.

**B. "Top stories" means importance within freshness.** For readers without
preferences, the rail shows the highest-`importance` live stories from the
last 24 hours (editor `importance_override` HIGH first, per ADR-027). It
falls back to the latest stories when fewer than 4 qualify. If the owner
would rather not define it, the alternative is to rename the rail
"More latest" so it doesn't claim a ranking it doesn't have.

**C. Coverage targets set from observation, not guessed.** After two weeks
of Coverage-page data, the owner sets weekly floors, for example "≥ 3
student stories", "≥ 3 immigration stories" and "no publisher above 50% of
publications". The Coverage page then flags a missed floor. Until the
floors are set, the page shows the numbers and flags only concentration
above 50%, which is a display threshold, not a target.

**Out of scope, and unchanged:** source rights. Adding sources to fix
concentration still goes through the rights gate (`DISABLED` by default,
owner-approved evidence). This ADR approves no source.

## Consequences

- A needs a small migration and changes to public `/v1/config` and the web
  and mobile navigation. Topic IDs and links are preserved.
- B changes ranking for anonymous readers only. Personalised feeds are
  unchanged.
- C adds no automation. Floors are flags for an editor, never auto-publish
  triggers, so human review gates are untouched.
- Until this is decided, navigation keeps growing with whatever categories
  the model invents. The Coverage page makes that visible but doesn't stop it.

## Alternatives considered

- **Constrain the classifier to a fixed category list.** This would stop
  sprawl at the source, but it changes the AI contract and the eval set,
  and it loses topic detail admins use for filtering. A mapping layer gets
  the reader-facing benefit without either cost.
- **Merge or rename existing topics in place.** This breaks saved
  preferences, alert subscriptions and public URLs.
- **Auto-select "Top stories" by source count alone.** This rewards
  whichever publisher runs the most section feeds, which is the
  concentration R8 is about.
