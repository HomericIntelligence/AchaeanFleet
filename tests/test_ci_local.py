"""Exercise the real CI dispatcher with controlled engine and tool boundaries.

These tests verify dispatch and failure propagation. They do not claim that
containerized linters, scanners, Python tests or BATS tests have passed.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SUBSETS = (
    "lint", "markdownlint", "pixi-check", "unit-tests", "integration-tests",
    "schema-validation", "security-secrets-scan", "security-dependency-scan",
    "deps-version-sync", "forbid-suppressions", "justfile-check", "symlink-check",
)

TOOL = r'''import json, os, pathlib, subprocess, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["CALLS"], "a") as output:
    output.write(json.dumps([name, *args]) + "\n")
if name == os.environ.get("FAIL_TOOL"):
    print("controlled tool failure: " + name, file=sys.stderr)
    raise SystemExit(37)
if name == "pixi" and args and args[0] == "run":
    args = args[1:]
    if args[:1] in (["--environment"], ["-e"]):
        args = args[2:]
    os.execvp(args[0], args)
'''

ENGINE = r'''import json, os, pathlib, subprocess, sys
args = sys.argv[1:]
with open(os.environ["ENGINES"], "a") as output:
    output.write(json.dumps(args) + "\n")
if args[:2] == ["image", "inspect"]:
    raise SystemExit(int(os.environ.get("IMAGE_EXIT", "0")))
if not args or args[0] != "run":
    raise SystemExit("unexpected engine operation")
if os.environ.get("ENGINE_EXIT"):
    raise SystemExit(int(os.environ["ENGINE_EXIT"]))
image_index = args.index("achaeanfleet-ci:local")
command = args[image_index + 1:]
assert command[0] == "bash", command
# The engine boundary supplies its private container environment. Do not read
# the host's login profile; preserve the command's other shell flags.
command = ["/bin/bash", *["-c" if arg == "-lc" else arg for arg in command[1:]]]
environment = dict(os.environ)
environment["PATH"] = os.environ["TOOL_PATH"]
raise SystemExit(subprocess.run(command, cwd=os.environ["FIXTURE_ROOT"], env=environment).returncode)
'''


class LocalCIContract(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="ci contract ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "project with spaces"
        (self.project / "scripts").mkdir(parents=True)
        shutil.copyfile(ROOT / "scripts" / "run_ci_local.sh", self.project / "scripts" / "run_ci_local.sh")
        for directory in ("tests", "nomad", "compose"):
            (self.project / directory).mkdir()
        (self.project / "nomad" / "fixture.hcl").write_text('job "fixture" {}\n')
        (self.project / "scripts" / "check-symlinks.sh").write_text('#!/bin/bash\nexec symlink-check\n')
        (self.project / "justfile").write_text('default:\n    true\n')
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls = self.root / "calls.jsonl"
        self.engines = self.root / "engines.jsonl"
        for name in ("pixi", "pre-commit", "markdownlint-cli2", "markdownlint",
                     "python", "bats", "docker-compose", "nomad", "gitleaks",
                     "trivy", "just", "hadolint", "yamllint", "git", "symlink-check"):
            path = self.bin / name
            path.write_text(f"#!{sys.executable}\n" + TOOL)
            path.chmod(0o700)
        self.engine = self.bin / "podman"
        self.engine.write_text(f"#!{sys.executable}\n" + ENGINE)
        self.engine.chmod(0o700)
        home = self.root / "home"
        home.mkdir()
        self.environment = {
            "PATH": str(self.bin) + ":/usr/bin:/bin", "HOME": str(home),
            "TMPDIR": str(self.root), "LANG": "C", "LC_ALL": "C",
            "CONTAINER_ENGINE": str(self.engine), "FIXTURE_ROOT": str(self.project),
            "TOOL_PATH": str(self.bin) + ":/usr/bin:/bin",
            "CALLS": str(self.calls), "ENGINES": str(self.engines),
        }

    def run_ci(self, subset: str | None = None, **environment: str) -> subprocess.CompletedProcess[str]:
        arguments = ["/bin/bash", str(self.project / "scripts" / "run_ci_local.sh")]
        if subset is not None:
            arguments.append(subset)
        return subprocess.run(arguments, cwd=self.project, env={**self.environment, **environment},
                              text=True, capture_output=True, timeout=10)

    def tool_calls(self) -> list[list[str]]:
        if not self.calls.exists():
            return []
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def test_all_and_default_execute_every_supported_stage(self) -> None:
        for subset in ("all", None):
            with self.subTest(subset=subset):
                self.calls.unlink(missing_ok=True)
                result = self.run_ci(subset)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                names = {call[0] for call in self.tool_calls()}
                self.assertTrue({"pre-commit", "markdownlint-cli2", "pixi", "python", "bats",
                                 "docker-compose", "nomad", "gitleaks", "trivy", "just",
                                 "symlink-check"}.issubset(names), names)

    def test_engine_failure_propagates_for_every_subset(self) -> None:
        for subset in SUBSETS:
            with self.subTest(subset=subset):
                result = self.run_ci(subset, ENGINE_EXIT="37")
                self.assertEqual(result.returncode, 37, result.stdout + result.stderr)

    def test_failed_validator_cannot_report_success(self) -> None:
        cases = (
            ("lint", "pre-commit"), ("markdownlint", "markdownlint-cli2"),
            ("pixi-check", "pixi"), ("unit-tests", "python"), ("unit-tests", "bats"),
            ("integration-tests", "docker-compose"), ("schema-validation", "python"),
            ("schema-validation", "nomad"), ("security-secrets-scan", "gitleaks"),
            ("security-dependency-scan", "trivy"), ("deps-version-sync", "python"),
            ("forbid-suppressions", "pre-commit"), ("justfile-check", "just"),
            ("symlink-check", "symlink-check"),
        )
        for subset, tool in cases:
            with self.subTest(subset=subset, tool=tool):
                self.calls.unlink(missing_ok=True)
                result = self.run_ci(subset, FAIL_TOOL=tool)
                self.assertIn(tool, [call[0] for call in self.tool_calls()], result.stdout + result.stderr)
                self.assertEqual(result.returncode, 37, result.stdout + result.stderr)
                self.assertIn("controlled tool failure: " + tool, result.stderr)

    def test_all_stops_after_python_failure(self) -> None:
        result = self.run_ci("all", FAIL_TOOL="python")
        self.assertEqual(result.returncode, 37, result.stdout + result.stderr)
        names = [call[0] for call in self.tool_calls()]
        self.assertIn("python", names)
        self.assertNotIn("bats", names)
        self.assertNotIn("docker-compose", names)
        self.assertNotIn("gitleaks", names)

    def test_unit_tests_include_python_and_recursive_bats(self) -> None:
        result = self.run_ci("unit-tests")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = self.tool_calls()
        self.assertTrue(any(call[:4] == ["python", "-m", "pytest", "tests/"] for call in calls), calls)
        self.assertIn(["bats", "-r", "tests"], calls)

    def test_dependency_scanner_is_a_failing_gate(self) -> None:
        result = self.run_ci("security-dependency-scan")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        invocation = next(call for call in self.tool_calls() if call[0] == "trivy")
        self.assertIn("HIGH,CRITICAL", invocation)
        self.assertIn("--exit-code", invocation)
        self.assertEqual(invocation[invocation.index("--exit-code") + 1], "1")

    def test_unknown_subset_and_missing_image_fail(self) -> None:
        self.assertNotEqual(self.run_ci("not-a-subset").returncode, 0)
        self.assertNotEqual(self.run_ci("unit-tests", IMAGE_EXIT="1").returncode, 0)
        self.assertEqual(self.tool_calls(), [])


if __name__ == "__main__":
    unittest.main()
