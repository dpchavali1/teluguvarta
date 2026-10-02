# T19-release — verify the deployed revision and key routes

Owner-requested 2026-10-02 release follow-up to T19. The VPS deploy script
currently checks service liveness but cannot distinguish a stale container from
the requested Git revision, and it did not catch a missing `/coverage` route.
Carry the exact Git SHA into API, admin and web containers; expose a bounded,
non-secret revision probe; show the short revision in the signed-in admin
navigation. The deploy/monitor gate must compare each running service to the
checkout SHA and check admin review/coverage and public search routes. Keep
the existing auth and editorial gates intact. Do not introduce new services or
persist secrets in probe output.

Acceptance: a current stack and routes pass; a stale revision, missing route,
or unavailable service fails the gate with a clear error. Shell syntax and
failure-path tests pass, and API/admin/web tests or builds scoped to changes
pass. The live VPS release/restore proof still requires host evidence.
