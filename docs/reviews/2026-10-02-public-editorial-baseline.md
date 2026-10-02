# Public editorial baseline — 2026-10-02

Read-only sample of the latest 300 items returned by the public
`GET /v1/stories?limit=100` cursor pages on 2026-10-02. Publication timestamps
span 2026-10-01 06:04 UTC to 2026-10-02 12:02 UTC. More pages existed. This is
a recent-feed snapshot, not a complete audit of the database or ingestion
pipeline. Publisher names below are approximated from the first public source
URL's hostname; multi-source stories and syndicated feeds can differ from the
admin Coverage report's attribution.

| Signal | Recent public sample |
|---|---:|
| Stories sampled | 300, all `FULL` |
| First-source URL on `ntnews.com` | 124 (41%) |
| First-source URLs on four leading domains (`ntnews.com`, `telugu360.com`, `ntvtelugu.com`, `telugutimes.net`) | 272 (91%) |
| Tagged entertainment / politics / tollywood | 103 / 84 / 78 (tags overlap) |
| Tagged NRI / diaspora / education | 8 / 1 / 16 |
| Tagged immigration / visa / student | 0 / 0 / 0 |
| Telugu variant QA `PASSED` / missing | 250 / 50 |
| Sensitive category | 299 `NONE`, 1 `FINANCIAL` |

The sample suggests a publisher and subject mix worth checking in the admin
Coverage dashboard. A missing Telugu variant does not by itself prove a failed
translation: it could be pending, withheld, or intentionally unavailable.
Topic tags are not mutually exclusive and can be incomplete. No source rights
or publication-policy change follows from these counts.

Next editorial checks, in order:

1. In admin Coverage, compare incoming items, holds and published stories by
   source/topic across several UTC-day ranges. Investigate whether practical
   NRI/student/visa material is absent upstream, held during generation, or
   misclassified. Record the reason before changing a source or taxonomy.
2. Review a native-speaker sample of published English/Telugu pairs and a
   sample of English-only stories. Check factual fidelity, usefulness of
   “why it matters,” correction state and Telugu QA lifecycle.
3. Use the existing rights review and human-approval rules for any source
   additions or immigration/legal/financial/breaking story. ADR-030 remains
   required for a reader-facing taxonomy/navigation change.

No private admin data, unpublished story text, source permission or production
setting was accessed or changed in this baseline.
