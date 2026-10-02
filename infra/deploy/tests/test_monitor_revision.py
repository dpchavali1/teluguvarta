"""Release probes fail when a route is absent or a container is stale."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


MONITOR = Path(__file__).resolve().parents[1] / "monitor.sh"
SHA = "a" * 40


class MonitorRevisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        deploy = root / "infra" / "deploy"
        deploy.mkdir(parents=True)
        shutil.copy2(MONITOR, deploy / "monitor.sh")
        (root / ".env.prod").write_text("")
        self.script = deploy / "monitor.sh"
        self.bin = root / "bin"
        self.bin.mkdir()
        self._command("git", f"#!/bin/sh\nprintf '%s\\n' '{SHA}'\n")
        self._command("docker", "#!/bin/sh\nexit 0\n")
        self._command("timeout", "#!/bin/sh\nshift\n\"$@\"\n")
        self._command(
            "curl",
            """#!/bin/sh
for arg do url="$arg"; done
case "$url" in
  *"${MOCK_FAIL_PATH:-/no-such-path}"*) exit 22 ;;
esac
case "$url" in
  */revision)
    case "$url" in
      *"${MOCK_STALE_SERVICE:-/no-such-service}"*) printf '%040d' 0 ;;
      *) printf '%s' '""" + SHA + """' ;;
    esac ;;
esac
""",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _command(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text(body)
        path.chmod(0o755)

    def run_monitor(self, **overrides: str) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}", "MONITOR_NO_PING": "1", **overrides}
        return subprocess.run(["bash", str(self.script)], env=env, text=True, capture_output=True, check=False)

    def test_current_revision_and_routes_pass(self) -> None:
        result = self.run_monitor()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_coverage_route_fails(self) -> None:
        result = self.run_monitor(MOCK_FAIL_PATH="/coverage")
        self.assertEqual(result.returncode, 1)
        self.assertIn("ADMIN_COVERAGE_MISSING", result.stdout)

    def test_stale_admin_revision_fails(self) -> None:
        result = self.run_monitor(MOCK_STALE_SERVICE="13001/revision")
        self.assertEqual(result.returncode, 1)
        self.assertIn("ADMIN_REVISION_MISMATCH", result.stdout)


if __name__ == "__main__":
    unittest.main()
