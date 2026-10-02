# Search pagination — T14-search

Public search accepts `q` (trimmed, 1–200 characters), `limit` (1–100, default
20), and an optional `cursor` (up to 512 characters). Responses retain `query`
and `items`, adding `next_cursor`: pass it with the same query for the next page;
null means no next page at the time of that request. Never treat returned length
as a total count. Invalid/mismatched cursors return 422; restart from page one.

Matching remains literal case-insensitive substring matching over English and
PASSED Telugu headline/summary, using the existing public statuses. Ordering
remains publication date descending (null last), then UUID ascending. The cursor
contains that boundary and a query hash; it is not an authorization token.
Every page reapplies the public/variant visibility gates. Requests fetch at most
limit + 1 stories and serialize at most limit. No offset or total-count query.

New rows ahead of the boundary do not shift later pages. This is a live view,
not a retained snapshot: publication-date changes, edits, withholding and removal
can change subsequent matches. Refresh/start over to see new leading results.
Normal website API caching still applies; this adds no cache expiry policy.

The website uses query-preserving SSR page links, retry of the failed page and
Back to first results. A new search starts without a cursor. The app appends
pages, deduplicates IDs (using the newer returned copy), retains existing results
and the cursor on a failed page, and ignores late pages after query changes,
clear or unmount. More results has explicit busy/disabled/retry states.

Older API responses missing next_cursor retain the existing 20-match guidance.
Deploy the API before or with web/app updates to enable paging; this change is
local until deployment/release evidence is recorded. No migration or new service.
Postgres relevance scoring and regional tagging remain separate improvements.

Verification commands and synthetic browser reproduction are recorded in
apps/web/README.md and PROGRESS.md. Fixtures establish paging behavior, not
production search relevance or TalkBack/VoiceOver acceptance.
