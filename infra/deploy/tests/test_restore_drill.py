"""Exercise host-script ownership and failure handling without production access.

Docker, age and date are controlled subprocess fakes. These tests validate the
drill orchestration, not archive compatibility or actual disaster recovery.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

DEPLOY = Path(__file__).resolve().parents[1]

DOCKER = r'''#!/usr/bin/env python3
import json, os, pathlib, re, sys, time
root = pathlib.Path(os.environ["FAKE_STATE"])
args = sys.argv[1:]
args = args[args.index("postgres") + 1:]
with (root / "commands.jsonl").open("a") as log:
    log.write(json.dumps(args) + "\n")
step = os.environ.get("FAIL_STEP")
if args[0] == "psql":
    sql = args[args.index("-c") + 1]
    match = re.search(r'(CREATE|DROP) DATABASE(?: IF EXISTS)? "([^"]+)"', sql)
    if match:
        action, db = match.groups()
        marker = root / db
        if action == "CREATE":
            if step == "create":
                marker.write_text("another run owns this database")
                sys.exit(1)
            marker.mkdir()
            if os.environ.get("PARALLEL"):
                deadline = time.monotonic() + 10
                while len(list(root.glob("restore_drill_*"))) < 2:
                    if time.monotonic() > deadline:
                        sys.exit(2)
                    time.sleep(0.02)
        else:
            if step == "drop": sys.exit(1)
            marker.rmdir()
    elif "alembic_version" in sql:
        db = args[args.index("-d") + 1]
        print("old_head" if step == "schema" and db != "teluguvarta" else "current_head")
    elif "count(*)" in sql:
        db = args[args.index("-d") + 1]
        print(0 if step == "data" and db != "teluguvarta" else 10)
    else:
        print("ops checks")
elif args[0] == "sh":
    path = root / pathlib.Path(args[-1]).name
    path.write_bytes(sys.stdin.buffer.read())
elif args[0] == "pg_restore":
    db = args[args.index("-d") + 1]
    path = root / pathlib.Path(args[-1]).name
    if step == "restore": sys.exit(1)
    assert path.name == db + ".dump", "dump must belong to this run"
    assert path.read_bytes() == b"archive", "only a complete decrypted dump may restore"
elif args[0] == "rm":
    if step == "remove": sys.exit(1)
    (root / pathlib.Path(args[-1]).name).unlink(missing_ok=True)
else:
    raise AssertionError(args)
'''

AGE = r'''#!/usr/bin/env python3
import os, sys
sys.stdout.buffer.write(b"partial" if os.environ.get("FAIL_STEP") == "decrypt" else b"archive")
sys.exit(1 if os.environ.get("FAIL_STEP") == "decrypt" else 0)
'''

DATE = r'''#!/usr/bin/env python3
from datetime import datetime, timezone
import sys
args = sys.argv[1:]
now = datetime(2026, 10, 1, 14, tzinfo=timezone.utc)
if "-d" in args:
    now = datetime.strptime(args[args.index("-d") + 1], "%Y%m%d %H:%M:%S").replace(tzinfo=timezone.utc)
fmt = args[-1]
print(int(now.timestamp()) if fmt == "+%s" else now.strftime(fmt.removeprefix("+").replace("%F", "%Y-%m-%d").replace("%T", "%H:%M:%S")))
'''

RECORD = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
with (pathlib.Path(os.environ["FAKE_STATE"]) / "records.jsonl").open("a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\n")
'''


class RestoreDrillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.deploy = self.root / "repo" / "infra" / "deploy"
        self.deploy.mkdir(parents=True)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.state = self.root / "state"
        self.state.mkdir()
        self.runs = self.root / "runs"
        self.runs.mkdir()
        self.backups = self.root / "backups"
        self.backups.mkdir()
        (self.backups / "teluguvarta_20261001T120000Z.dump.age").write_bytes(b"encrypted")
        self.identity = self.root / "test-identity"
        self.identity.write_text("test-only")
        (self.root / "repo" / ".env.prod").write_text("")
        for name in ["restore-drill.sh", "ops-evidence.sh"]:
            shutil.copy2(DEPLOY / name, self.deploy / name)
        for path, content in [
            (self.bin / "docker", DOCKER), (self.bin / "age", AGE),
            (self.bin / "date", DATE), (self.deploy / "ops-record.sh", RECORD),
        ]:
            path.write_text(content)
            path.chmod(0o755)
        self.env = {
            **os.environ, "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "FAKE_STATE": str(self.state), "BACKUP_DIR": str(self.backups),
            "BACKUP_AGE_IDENTITY": str(self.identity), "TMPDIR": str(self.runs),
            "OPS_EVIDENCE_REPORT_DIR": str(self.root),
        }
        self.env.pop("FAIL_STEP", None)
        self.env.pop("PARALLEL", None)

    def run_script(self, *args, step=None):
        env = {**self.env, **({"FAIL_STEP": step} if step else {})}
        return subprocess.run(
            ["bash", str(self.deploy / args[0]), *args[1:]], env=env,
            capture_output=True, text=True, timeout=20, check=False,
        )

    def lines(self, name):
        return [json.loads(line) for line in (self.state / name).read_text().splitlines()]

    def assert_failure(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("RESTORE DRILL PASSED", result.stdout)
        records = self.lines("records.jsonl")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0][:2], ["RESTORE_DRILL", "fail"])
        self.assertEqual(list(self.runs.iterdir()), [])

    def test_success_records_rto_rpo_only_after_owned_resources_removed(self):
        result = self.run_script("restore-drill.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record, = self.lines("records.jsonl")
        self.assertEqual(record[:2], ["RESTORE_DRILL", "ok"])
        self.assertIn("RTO 0s, RPO 120 min, schema current_head", record[2])
        self.assertEqual(list(self.state.glob("restore_drill_*")), [])
        self.assertEqual(list(self.runs.iterdir()), [])
        self.assertIn("RESTORE DRILL PASSED", result.stdout)

    def test_failed_create_never_drops_existing_database(self):
        result = self.run_script("restore-drill.sh", step="create")
        self.assert_failure(result)
        commands = self.lines("commands.jsonl")
        self.assertFalse(any("DROP DATABASE" in " ".join(command) for command in commands))
        self.assertFalse(any(command[0] == "rm" for command in commands))
        self.assertEqual(len(list(self.state.glob("restore_drill_*"))), 1)

    def test_decryption_failure_cleans_partial_dump_without_restoring(self):
        result = self.run_script("restore-drill.sh", step="decrypt")
        self.assert_failure(result)
        self.assertFalse(any(command[0] == "pg_restore" for command in self.lines("commands.jsonl")))
        self.assertEqual(list(self.state.glob("restore_drill_*")), [])

    def test_restore_failure_cleans_owned_resources(self):
        result = self.run_script("restore-drill.sh", step="restore")
        self.assert_failure(result)
        self.assertEqual(list(self.state.glob("restore_drill_*")), [])

    def test_cleanup_failure_cannot_report_success(self):
        for step in ["remove", "drop"]:
            with self.subTest(step=step):
                (self.state / "records.jsonl").unlink(missing_ok=True)
                result = self.run_script("restore-drill.sh", step=step)
                self.assert_failure(result)
                self.assertIn("CLEANUP FAILED", result.stderr)
                self.assertIn("cleanup failed=1", self.lines("records.jsonl")[0][2])

    def test_schema_or_missing_data_is_a_failed_drill(self):
        for step in ["schema", "data"]:
            with self.subTest(step=step):
                (self.state / "records.jsonl").unlink(missing_ok=True)
                self.assert_failure(self.run_script("restore-drill.sh", step=step))
                self.assertEqual(list(self.state.glob("restore_drill_*")), [])

    def test_concurrent_drills_use_distinct_databases_and_dump_paths(self):
        env = {**self.env, "PARALLEL": "1"}
        runs = [subprocess.Popen(
            ["bash", str(self.deploy / "restore-drill.sh")], env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ) for _ in range(2)]
        try:
            for run in runs:
                out, err = run.communicate(timeout=20)
                self.assertEqual(run.returncode, 0, out + err)
        finally:
            for run in runs:
                if run.poll() is None:
                    run.kill()
                    run.communicate()
        commands = self.lines("commands.jsonl")
        restored = [command for command in commands if command[0] == "pg_restore"]
        self.assertEqual(len(restored), 2)
        self.assertEqual(len({command[-1] for command in restored}), 2)
        self.assertEqual(len({command[command.index("-d") + 1] for command in restored}), 2)
        self.assertEqual([record[1] for record in self.lines("records.jsonl")], ["ok", "ok"])
        self.assertEqual(list(self.state.glob("restore_drill_*")), [])
        self.assertEqual(list(self.runs.iterdir()), [])

    def test_evidence_report_propagates_failed_requested_drill(self):
        (self.deploy / "restore-drill.sh").write_text("#!/usr/bin/env bash\nexit 9\n")
        result = self.run_script("ops-evidence.sh", "--drill")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("restore drill exited non-zero", result.stdout)
        self.assertIn("Report saved to", result.stdout)

    def test_read_only_evidence_report_does_not_run_a_drill(self):
        result = self.run_script("ops-evidence.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.state / "records.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
