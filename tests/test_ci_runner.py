"""Exercise local CI dispatch and failure propagation without a real engine."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LocalCITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        shutil.copyfile(ROOT / "scripts/run_ci_local.sh", self.root / "scripts/run_ci_local.sh")
        shutil.copyfile(ROOT / "scripts/check-symlinks.sh", self.root / "scripts/check-symlinks.sh")
        shutil.copyfile(ROOT / "justfile", self.root / "justfile")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "commands.jsonl"
        engine = self.bin / "podman"
        engine.write_text(
            f"#!{sys.executable}\n"
            "import json,os,subprocess,sys\n"
            "args=sys.argv[1:]\n"
            "with open(os.environ['CI_TEST_LOG'],'a') as f:f.write(json.dumps(args)+'\\n')\n"
            "if args[:2]==['image','inspect']:raise SystemExit(0)\n"
            "if args[0]!='run':raise SystemExit(2)\n"
            "at=args.index('bash')\n"
            "raise SystemExit(subprocess.call(args[at:]))\n"
        )
        engine.chmod(0o755)
        tool = (
            f"#!{sys.executable}\n"
            "import json,os,subprocess,sys\n"
            "from pathlib import Path\n"
            "name=Path(sys.argv[0]).name;args=sys.argv[1:]\n"
            "with open(os.environ['CI_TEST_LOG'],'a') as f:f.write(json.dumps([name,*args])+'\\n')\n"
            "if name==os.environ.get('CI_TEST_FAIL') and (not os.environ.get('CI_TEST_FAIL_ARGUMENT') or os.environ['CI_TEST_FAIL_ARGUMENT'] in args):raise SystemExit(7)\n"
            "if name=='pixi' and args[0]=='run':\n"
            " args=args[1:]\n"
            " while args and args[0].startswith('-'):\n"
            "  args=args[2:] if args[0] in ('-e','--environment') else args[1:]\n"
            " raise SystemExit(subprocess.call(args))\n"
        )
        for name in ("pixi", "pre-commit", "hadolint", "yamllint", "markdownlint-cli2", "markdownlint", "bats", "validate", "gitleaks", "trivy", "python", "python3", "just", "nomad", "docker-compose"):
            target = self.bin / name
            target.write_text(tool)
            target.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        CONTAINER_ENGINE=str(engine), CI_TEST_LOG=str(self.log),
                        HOME=str(self.root / "home"))

    def test_ci_build_preserves_engine_failure_without_docker_retry(self):
        for name in ("podman", "docker"):
            target = self.bin / name
            target.write_text(
                f"#!{sys.executable}\n"
                "import json,os,sys\n"
                "from pathlib import Path\n"
                "with open(os.environ['CI_TEST_LOG'],'a') as f:f.write(json.dumps([Path(sys.argv[0]).name,*sys.argv[1:]])+'\\n')\n"
                "raise SystemExit(7 if Path(sys.argv[0]).name=='podman' else 0)\n"
            )
            target.chmod(0o755)
        result = subprocess.run([shutil.which("just"), "--justfile", str(self.root / "justfile"), "ci-build"],
                                cwd=self.root, env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(any(call[0] == "docker" for call in self.commands()))

    def run_ci(self, subset, failure=""):
        self.env["CI_TEST_FAIL"] = failure
        return subprocess.run(["bash", str(self.root / "scripts/run_ci_local.sh"), subset],
                              cwd=self.root, env=self.env, capture_output=True, text=True)

    def commands(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_all_selects_python_shell_and_security_checks(self):
        result = self.run_ci("all")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        commands = self.commands()
        for name in ("python", "bats", "gitleaks", "trivy", "pre-commit"):
            self.assertTrue(any(call[0] == name for call in commands), name)
        for mode in ("build", "test", "package", "install", "release"):
            self.assertTrue(any(call[:3] == ["python", "scripts/check_ci_structure.py", mode]
                                for call in commands), mode)

    def test_all_stops_on_schema_test_failure(self):
        self.env["CI_TEST_FAIL_ARGUMENT"] = "tests/test_nomad_specs.py"
        result = self.run_ci("all", "python")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(any(call[0] == "gitleaks" for call in self.commands()))

    def test_unit_lane_runs_python_and_every_shell_suite(self):
        result = self.run_ci("unit-tests")
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.commands()
        self.assertTrue(any(call[:3] == ["python", "-m", "pytest"] for call in commands))
        self.assertTrue(any(call[0] == "bats" and "-r" in call and "tests" in call for call in commands))

    def test_real_tool_failures_fail_the_lane(self):
        for subset, tool in (("lint", "pre-commit"), ("markdownlint", "markdownlint-cli2"),
                             ("unit-tests", "bats"), ("integration-tests", "docker-compose"),
                             ("security-secrets-scan", "gitleaks"), ("security-dependency-scan", "trivy")):
            with self.subTest(subset=subset):
                result = self.run_ci(subset, tool)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_compose_lane_validates_documented_caddy_combinations(self):
        result = self.run_ci("integration-tests")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [call for call in self.commands() if call[0] == "docker-compose"]
        for overlay in ("mesh", "claude-only"):
            self.assertIn(["docker-compose", "-f", "compose/docker-compose.caddy.yml",
                           "-f", f"compose/docker-compose.{overlay}.yml", "config", "--quiet"], calls)
        self.assertIn(["docker-compose", "-f", "compose/docker-compose.smoke.yml", "config", "--quiet"], calls)

    def test_container_is_bounded_and_does_not_mount_host_home(self):
        result = self.run_ci("unit-tests")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [call for call in self.commands() if call[0] == "run"]
        self.assertTrue(calls)
        for call in calls:
            self.assertTrue(any(arg.startswith("--cpus=") for arg in call))
            self.assertTrue(any(arg.startswith("--memory=") for arg in call))
            self.assertFalse(any(arg.startswith(self.env["HOME"] + ":") for arg in call))


if __name__ == "__main__":
    unittest.main()
