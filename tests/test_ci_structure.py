"""Exercise the shared lightweight CI checks against actual source fixtures."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CHECKER = Path(__file__).resolve().parents[1] / "scripts/check_ci_structure.py"


class StructureChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, content in {
            "bases/Dockerfile.node": "FROM node:26\nENTRYPOINT [\"/entrypoint.sh\"]\n",
            "vessels/aider/Dockerfile": "ARG BASE_IMAGE=achaean-base-node\nFROM ${BASE_IMAGE}\n",
            "tests/entrypoint.bats": '@test "fixture" { true; }\n',
            "scripts/check.sh": "#!/bin/sh\nexit 0\n",
            ".github/workflows/release.yml": 'tags:\n  - "v*.*.*"\nfile: vessels/aider/Dockerfile\npush: true\nname: Validate tag matches semver\n',
        }.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

    def check(self, mode):
        return subprocess.run([sys.executable, str(CHECKER), mode, "--root", str(self.root)],
                              capture_output=True, text=True)

    def test_all_five_modes_accept_valid_sources_including_aider(self):
        for mode in ("build", "test", "package", "install", "release"):
            with self.subTest(mode=mode):
                result = self.check(mode)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_package_rejects_a_vessel_without_from(self):
        (self.root / "vessels/aider/Dockerfile").write_text("RUN true\n")
        self.assertNotEqual(self.check("package").returncode, 0)

    def test_shell_syntax_failure_fails_test_mode(self):
        (self.root / "scripts/check.sh").write_text("if ; then\n")
        self.assertNotEqual(self.check("test").returncode, 0)

    def test_install_rejects_missing_entrypoint_and_legacy_base(self):
        (self.root / "vessels/aider/Dockerfile").write_text("FROM scratch\n")
        self.assertNotEqual(self.check("install").returncode, 0)

    def test_release_rejects_missing_referenced_vessel(self):
        (self.root / "vessels/aider/Dockerfile").unlink()
        self.assertNotEqual(self.check("release").returncode, 0)


if __name__ == "__main__":
    unittest.main()
