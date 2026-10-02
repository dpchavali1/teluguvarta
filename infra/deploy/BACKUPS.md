# Production backups (single-VPS deploy)

- **What:** a nightly `pg_dump` of the live Postgres. It is encrypted with
  [age](https://age-encryption.org) as it streams, so no plaintext copy is ever
  written to disk.
- **Where:** kept on the server for 14 days in `/var/backups/teluguvarta`. Also
  copied to a Hetzner Storage Box and kept there for 30 days.
- **Before deploys:** `deploy.sh` takes an extra backup before every migration.

Scripts:
- `backup-prod.sh` makes one backup.
- `restore-drill.sh` proves a backup restores.
- `deploy.sh` installs `age` and the cron job at `/etc/cron.d/teluguvarta-backup`
  (03:30 server time) once `BACKUP_AGE_RECIPIENT` is set.

## One-time setup

1. **Encryption key — on your laptop, not the server**
   ```
   age-keygen -o teluguvarta-backup.key      # prints "Public key: age1..."
   ```
   Store `teluguvarta-backup.key` in your password manager. It is the only way
   to read a backup, so never put it on the server except during a drill.
2. **Storage Box**
   1. In Hetzner Robot/Console, create a Storage Box (BX11 is enough).
   2. Enable **SSH support**.
   3. Note the username, e.g. `u123456`.
   4. On the server:
      ```
      ssh-keygen -t ed25519 -N '' -f /root/.ssh/storagebox
      cat /root/.ssh/storagebox.pub | ssh -p 23 u123456@u123456.your-storagebox.de install-ssh-key
      ```
3. **Configure** — in `/opt/teluguvarta/.env.prod`:
   ```
   BACKUP_AGE_RECIPIENT=age1...                        # the public key from step 1
   BACKUP_STORAGE_BOX=u123456@u123456.your-storagebox.de
   BACKUP_HEALTHCHECK_URL=https://hc-ping.com/<uuid>   # optional, alerts if backups stop
   ```
   Optional settings, with their defaults:
   - `BACKUP_KEEP_DAYS_LOCAL=14`
   - `BACKUP_KEEP_DAYS_REMOTE=30`
   - `BACKUP_SSH_KEY=/root/.ssh/storagebox`
4. **Apply** — run `sudo ./infra/deploy/deploy.sh`. Then take a first backup
   right away with `sudo ./infra/deploy/backup-prod.sh`.

## Restore drill (do it once now, then monthly)

1. Copy the key onto the server for the drill only:
   ```
   scp teluguvarta-backup.key root@<server>:/root/drill-key.txt
   ```
2. Run the drill:
   ```
   sudo BACKUP_AGE_IDENTITY=/root/drill-key.txt ./infra/deploy/restore-drill.sh
   ```
3. Delete the key again:
   ```
   shred -u /root/drill-key.txt
   ```

What the drill does:
- Restores the newest backup into a throwaway `restore_drill_<random suffix>` database,
  never the live one.
- Reserves a distinct database name and container plaintext dump path for each
  run, including simultaneous drills. Cleanup drops only a database this run
  successfully created.
- Compares the schema version and row counts with the live database.
- Prints the restore time (RTO) and the backup's age (RPO).
- Drops the throwaway database.
- Reports success and records `RESTORE_DRILL` only after validation and cleanup
  succeed. Failed decryption, restore, comparison or cleanup exits nonzero and
  records failure; cleanup errors print the remaining database/dump path.

Record the result in `PROGRESS.md`.

Local orchestration regressions run without Docker, production credentials or an
encryption key:

```sh
python3 -m unittest discover -s infra/deploy/tests -v
```

These subprocess-fake tests cover concurrency, database ownership and failure
reporting. They do not replace the real monthly restore drill or verify archive
compatibility, RTO/RPO or production recovery.

To restore a backup from the Storage Box, first copy it down:
```
rsync -e 'ssh -p 23 -i /root/.ssh/storagebox' \
  u123456@u123456.your-storagebox.de:teluguvarta/<file> /var/backups/teluguvarta/
```

## Real disaster recovery (live DB lost)

1. Stop the api and worker containers.
2. Restore the newest backup into a new database. Decrypt it to a file first:
   dumps are written to a pipe, so `pg_restore` must read them from a seekable
   file, not from stdin. Follow the same steps as `restore-drill.sh`.
3. Rename databases so the restored one becomes `teluguvarta`.
4. Start the api and worker again.

Also keep a copy of `.env.prod`. It holds `MFA_SECRET_ENCRYPTION_KEY`, and
without it the restored admins' MFA secrets cannot be decrypted.
