# Release preflight — 2026-10-01

This is evidence collected for T19 after the owner requested release and
recovery proof. It is **not production acceptance**. No production deployment,
restore, alert injection or rollback was run from this checkout.

## Known local/GitHub state

- Local `main` started clean at `fa780eb`; no production revision is known.
- The GitHub CI run for that revision
  [failed](https://github.com/dpchavali1/teluguvarta/actions/runs/36957815694):
  contracts passed; API SAST and Node dependency scan failed. The SAST finding
  was a type-only `xml.etree.ElementTree.Element` import in the already
  defused RSS adapter. A small structural type protocol removes the banned
  import; local `bandit -r app -c pyproject.toml`, mypy and ruff now pass.
- The dependency scan reports high-severity node-forge 1.4.0 in Expo CLI's
  transitive code-signing chain. The advisory lists no patched package version
  as of this check. Do not turn off the scan or mark CI green to deploy.
  Recheck the upstream advisory and Expo update; otherwise record a scoped
  security decision before accepting a remaining high finding.
- `bash -n` passes for deploy, evidence, backup and restore scripts. Ten
  simulated restore/alert-report tests pass. A requested alert test now exits
  nonzero if delivery or receipt is unconfirmed. These tests do not prove a
  real backup restores or an alert reaches a person.
- Focused X/RSS regressions pass (17 tests) against local scratch databases;
  the full API suite passes (564 tests, 10 warnings). Web/contracts and native
  typechecks, 74 native tests/14 suites and Android/iOS export pass. No live
  X call or production data change occurred.

## Production evidence still required

1. Resolve [ADR-036](../adr/ADR-036-production-deployment-topology.md):
   identify the actual host/project and an access path. ADR-007's managed
   platforms and the later single-VPS scripts conflict.
2. Get a green release CI or a documented resolution of the high advisory.
   Record the exact revision being deployed.
3. Confirm a recent, offsite, encrypted backup and off-server copy of MFA
   decryption material. Record age without disclosing keys.
4. Deploy matching API/admin/web versions and run migrations using the
   confirmed topology. Check public search pagination, Telugu repair,
   account deletion, MFA/logout, health and worker/queue state.
5. Run a real isolated restore drill; record RTO/RPO, schema and row-count
   checks, and cleanup. Test alert receipt and rollback in that environment.
6. Keep T19 partial until production/device and editorial gates in
   `PROGRESS.md` are verified.
