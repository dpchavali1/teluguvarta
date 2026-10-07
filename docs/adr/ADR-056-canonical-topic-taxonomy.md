# ADR-056: Fixed topic taxonomy and a topic-alert floor at the importance base

- **Status**: accepted
- **Date**: 2026-10-06
- **Ticket**: owner device feedback (duplicate topics, few alerts)

## Context

The classifier was asked for free-form "categories", and `_link_topics`
created a new active topic for every new phrasing. On 2026-10-06 production
had 243 active topics. About 160 of them had at most one story, for example
`crime`, `crime-safety`, `crime-and-justice`, `law-and-order` and
`police-and-crime`. Readers chose from that list. A reader with 74 topics
selected rarely matched a new story, because the next story usually got yet
another variant.

Separately, every story starts at importance 0.4 (`app/content/importance.py`),
and topic, keyword, place and digest alerts required 0.5. Only urgent,
multi-source or audience-priority stories cleared that. On 2026-10-06, 6 of
the latest 100 live stories did.

## Decision

1. `app/content/topics.py` holds the only topic taxonomy: 27 general topics
   (the previously seeded slugs plus politics, government & welfare, India,
   US news, world, business, technology, health, crime & safety, courts &
   legal, agriculture, infrastructure, weather & environment, and
   culture & religion) and the 13 student topics. Tollywood, cinema and OTT
   are part of Entertainment.
2. The classifier prompt lists these slugs. Off-list output is mapped through
   `TOPIC_ALIASES` or dropped. Topics are never created at runtime.
3. Migration `f6a2c8e4b1d7` seeds the taxonomy and moves stories and reader
   subscriptions from each retired slug onto its canonical topic. When
   several subscriptions merge, the most immediate urgency wins. Links to
   slugs with no single home (such as `local-news`) are dropped, and every
   non-canonical topic is deactivated. The migration's downgrade only
   reactivates topics; the merge itself cannot be undone.
4. `PATCH /v1/me/preferences` maps retired slugs from older app builds onto
   canonical ones and accepts only active topics. `/v1/config` publishes
   `topic_aliases`, and the app's Alerts screen remaps stored selections
   once.
5. `TOPIC_ALERT_MIN_IMPORTANCE` drops from 0.5 to 0.4. Any story in a topic
   the reader selected can alert. An editor's LOW override (0.2) still
   blocks it, and the reader's daily cap and quiet hours still bound volume.
   The breaking-alert path is unchanged.

## Consequences

- Topic lists are short and stable, and subscriptions match new stories.
- A reader who selects many topics will usually reach the daily cap (default
  5). The cap defers the excess to the next local day, so heavy readers may
  want a higher cap or digest urgency for broad topics.
- Readers subscribed only to dropped topics (`local-news`, `regional-news`,
  `state-news`) lose that subscription. Place follows (ADR-043) are the
  replacement for state/city scope.
- Adding a topic now means editing `app/content/topics.py` and a migration
  that inserts it. The classifier cannot add topics.

## Alternatives considered

- **Embedding similarity to merge topics at runtime**: still yields an
  unbounded list and nondeterministic merges.
- **Admin-curated merges with the free-form classifier left in place**: the
  duplicates would keep returning, so editors would merge forever.
- **Keeping the 0.5 floor**: matching would work, but most stories would
  still never alert.
