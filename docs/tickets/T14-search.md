# T14 search — bounded pagination (R12 follow-up)

Depends on T14/T15 and the implemented UI05/UI09 search recovery. Owner
authorized sequential improvement-plan implementation on 2026-10-01.
Status: implemented locally; final verification in PROGRESS. Deployment and
native device acceptance remain pending.

Keep the current public-story and displayable EN/TE substring matching rules,
literal wildcard escaping, publication-date/UUID ordering, rate limit and
anonymous browsing. Add an optional next cursor to SearchResponse and cursor
input to search. Fetch at most the requested page size plus one (existing
1–100 bound, default 20). Use publication-date/UUID keyset boundaries so inserts
ahead of the current page do not shift subsequent pages. Support null dates.
Validate bounded cursors and bind them to the trimmed query; reject malformed or
mismatched cursors explicitly. Bound query length to 200 characters.

Pagination is a live view, not a retained snapshot: edits/removals or changes to
publication dates can change later pages. No exact total-count claim, new
geographic inference, search ranking policy, migration or infrastructure.
Postgres relevance and regional tagging remain separately scoped follow-ups.

Web: SSR page links preserve query/cursor; new query starts at page one. Provide
first-page recovery and preserve the failed page on retry. App: explicit More
results, append/deduplicate by story ID, retain rows/cursor on paging failure,
retry, busy feedback, and ignore late pages after query changes/clear/unmount.
Use generated contracts; preserve compatibility with older missing-cursor API
responses by retaining the existing cap guidance.

Acceptance: real-Postgres paging/ties/nulls/end-page/EN/TE/hidden QA and status/
literal wildcards/malformed and mismatched cursors/insertion/removal tests;
native component tests for append/busy/retry/stale responses; generated schema
and types match. Scoped API lint/mypy/tests, web lint/typecheck/test/build and
fixture browser navigation/overflow/axe/screenshots; mobile typecheck/tests and
Android/iOS export. Update progress/plan; deployment and native device acceptance
remain separate. No production changes or provider calls.
