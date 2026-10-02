# X account activation handoff

The worker already schedules `x_official_account_fetch` for an active,
`LINK_ONLY` X source with a linked account and polling cadence. It uses the
official X API, persists `since_id`, deduplicates posts, and routes them
through the same classify, draft, translation, and editorial flow as news.
Immigration, legal, financial, and breaking stories always enter human review;
an automatic X poll is **not** automatic publication.

## Candidate accounts to review

These are discovery candidates, not an approved source allowlist:

| Candidate | Agency evidence | Review note |
|---|---|---|
| `@USCIS` | [USCIS social presence](https://www.uscis.gov/) | Confirm the current handle through an agency-owned page and the X API's stable numeric user ID before linking; the search evidence did not establish that pair conclusively. |
| `@TravelGov` | [State Department travel-industry page](https://travel.state.gov/en/international-travel/planning/guidance/travel-industry.html) | Agency page explicitly names the handle. It covers travel broadly, so each post still needs relevance screening. |
| `@StudyinStates` | [ICE official social account directory](https://www.ice.gov/newsroom/social) | Student/SEVP focus; verify the numeric ID and scope. |
| `@ICEgovERO` | [ICE official social account directory](https://www.ice.gov/newsroom/social) | Enforcement focus; likely many posts are outside reader scope. Review before deciding whether to add. |

## Activation sequence

1. Confirm the production API/worker topology and deploy a compatible revision
   (ADR-036). The GitHub push alone does not update the running worker.
2. Obtain X API access and put the bearer token in the **server-side worker
   secret configuration** as `X_API_BEARER_TOKEN`. Set
   `X_API_COST_PER_POST_USD` and `MONTHLY_X_API_BUDGET_USD` from the current X
   pricing and the owner's spending limit. Never enter a bearer token in the
   admin UI, mobile app, repository, or chat.
3. In Admin → Sources, add an **X account** source. It starts disabled. Link
   the agency's verified handle and numeric X user ID with a conservative
   cadence (for example, 30 minutes) and `LOW` budget priority. Obtain the
   numeric ID via the official X API or developer console, not a third-party
   scraper.
4. An ADMIN reviews the account's official ownership, X terms/API rights,
   permitted internal evidence fields and attribution policy. Record the
   evidence URL, reviewer and restrictions in the existing source-rights
   form. Only then set `LINK_ONLY` and active. This is the same ADR-002 gate
   as every other source.
5. Confirm a successful poll and advancing `since_id` in Admin →
   Observability. Check X cost and errors there. Inspect resulting drafts in
   the editorial queue. Approve relevant immigration/visa stories manually;
   published stories then enter the public news feed and link to the exact X
   post. Pause an account by making its source inactive.

Production activation is still pending X API credentials, reviewed numeric
user IDs and rights evidence, deployment topology, and editor workflow
readiness. No candidate was enabled during this change.
