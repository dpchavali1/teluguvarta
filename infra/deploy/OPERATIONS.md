# Operating the single-VPS deploy

Backups and restore: [BACKUPS.md](BACKUPS.md). This file covers monitoring,
what a deploy checks, and rollback. Background: review 2026-09-29 #9.

## Health checks

| Check | How | Failure line |
|---|---|---|
| API up and reaching Postgres | `GET /health/ready` → 200, or 503 if the DB is unreachable (`/health` stays a plain liveness check) | `API_NOT_READY` |
| Worker alive | `python -m app.jobs.monitor`, run in the **api** container: some job claimed in the last 10 min, or one holding a live lease | `WORKER_STALE` |
| Queue keeping up | no due `PENDING` job older than 15 min | `QUEUE_BACKLOG` |
| Web and admin answer | HTTP to ports 13000 / 13001 on localhost | `WEB_DOWN`, `ADMIN_DOWN` |

`infra/deploy/monitor.sh` runs all of them. It is used in two places:
- **Cron**, every 5 minutes (`/etc/cron.d/teluguvarta-monitor`, log
  `/var/log/teluguvarta-monitor.log`). It skips runs while a deploy is in
  progress (`/run/teluguvarta-deploying`).
- **`deploy.sh`**, as its final gate. The deploy exits 1 with the failing
  lines if they don't all pass within 2 minutes.

The api container also has a Compose healthcheck on `/health/ready`, so
`docker compose ps` shows `healthy`/`unhealthy`.

The worker's own alerts (`app/alerts.py`, sent to `ALERT_WEBHOOK_URL`) cover
budget, source and job error rates. They can't report the worker being gone,
which is why this check runs outside it.

## External alerting (one-time setup)

Nothing on the server can report the server itself being down, so alerts come
from a dead-man's switch:

1. Create a check at [healthchecks.io](https://healthchecks.io) (the free tier
   is enough). Set the period to 5 min and the grace to 10 min. Add your email
   or phone as the integration.
2. Put its ping URL in `.env.prod`:
   ```
   MONITOR_HEALTHCHECK_URL=https://hc-ping.com/<uuid>
   ```
   `monitor.sh` reads it on every run, so no redeploy is needed.
3. Test the alert: `sudo docker compose -f infra/deploy/docker-compose.prod.yml --env-file .env.prod stop worker`,
   then wait about 15 min for the alert. Start the worker again.

Each run pings the URL on success. A failed run posts the failure lines to
`<url>/fail`. If no ping arrives for 15 min (VPS down, cron dead, Docker
wedged), healthchecks.io alerts on its own.

## Rollback

Deploys are git-based. `deploy.sh` resets to `origin/main` unless you pass
`NO_PULL=1`. `PROGRESS.md` records the revision of each production deploy.

1. On the server, in `/opt/teluguvarta`, pick the target commit, e.g. `abc1234`.
2. Check whether migrations changed since then:
   ```
   git diff --name-only abc1234 HEAD -- infra/migrations/versions
   ```
3. **No migration files listed:** just check out the old code.
   ```
   git checkout abc1234 && sudo NO_PULL=1 ./infra/deploy/deploy.sh
   ```
4. **New migrations listed:** downgrade the schema *first*, while the new code
   (which knows those revisions) is still checked out. After the checkout, the
   old code's `alembic upgrade head` can't find the newer revision in the DB.
   The target revision is the `down_revision` of the oldest new migration file.
   ```
   sudo docker compose -f infra/deploy/docker-compose.prod.yml --env-file .env.prod \
     run --rm api alembic downgrade <target revision>
   git checkout abc1234 && sudo NO_PULL=1 ./infra/deploy/deploy.sh
   ```
   A downgrade drops whatever the migration added: tables, columns, and rows
   using new statuses. Read the migration's `downgrade()` first. If a downgrade
   would lose data you need, or fails, restore the pre-migration backup
   `deploy.sh` took instead (BACKUPS.md, "Real disaster recovery"). That also
   loses writes made since the deploy.
5. Roll forward later with a plain `sudo ./infra/deploy/deploy.sh`. It resets to
   `origin/main` and re-applies the migrations.

## Readiness checklist (review #9 evidence)

`ops-evidence.sh` collects the evidence for this list without printing secret
values, and saves a copy under `/root/`:

```
sudo ./infra/deploy/ops-evidence.sh                 # settings, local + offsite backups, monitor log
sudo ./infra/deploy/ops-evidence.sh --test-alert    # also fire a TEST alert and record receipt
sudo BACKUP_AGE_IDENTITY=/root/drill-key.txt ./infra/deploy/ops-evidence.sh --drill
```

If a requested drill fails, `ops-evidence.sh --drill` still finishes the evidence
report but exits nonzero. Plain report mode only collects observations; a zero
exit is not acceptance of the checklist. `OPS_EVIDENCE_REPORT_DIR` can select an
existing writable report directory (default `/root`).
Likewise, `--test-alert` exits nonzero if the monitor URL is unset, the test
cannot be posted, or the recipient does not confirm receipt; the report still
finishes so the failure is visible.

Backups, the offsite copy, restore drills, monitor runs and confirmed alert
tests are also recorded in `ops_checks` (`ops-record.sh`), and admin
Observability shows each one's age, with "Overdue", "Failing" or "No record"
when it needs attention.

Record each item with its date in `PROGRESS.md`:

- [ ] `BACKUP_AGE_RECIPIENT` and `BACKUP_STORAGE_BOX` set; first backup taken; the file is visible on the Storage Box.
- [ ] Restore drill passed (`restore-drill.sh`); RTO/RPO recorded.
- [ ] A copy of `.env.prod` kept off the server (password manager). It holds
      `MFA_SECRET_ENCRYPTION_KEY`, so without it a restored database's admin MFA can't be decrypted.
- [ ] `MONITOR_HEALTHCHECK_URL` set; the stopped-worker alert test above received.
- [ ] `BACKUP_HEALTHCHECK_URL` set, so a backup that stops running raises an alert.
