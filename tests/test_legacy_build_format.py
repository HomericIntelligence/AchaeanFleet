"""Legacy build commands retain Docker-only health-check metadata in Podman."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LegacyBuildFormatTests(unittest.TestCase):
    def test_every_legacy_build_uses_healthcheck_capable_format(self):
        for recipe, expected_builds in (("build-bases", 3), ("build-vessel", 2), ("build-all", 12)):
            with self.subTest(recipe=recipe), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                binaries = root / "bin"
                binaries.mkdir()
                log = root / "calls.jsonl"
                engine = binaries / "podman"
                engine.write_text(
                    f"#!{sys.executable}\n"
                    "import json, os, sys\n"
                    "with open(os.environ['BUILD_TEST_LOG'], 'a') as stream:\n"
                    " stream.write(json.dumps({'args':sys.argv[1:], 'format':os.environ.get('BUILDAH_FORMAT')})+'\\n')\n"
                )
                engine.chmod(0o755)
                environment = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ["PATH"],
                                   BUILD_TEST_LOG=str(log), BUILDAH_FORMAT="oci")
                environment.pop("CONTAINER_CMD", None)
                command = [shutil.which("just"), recipe]
                if recipe == "build-vessel":
                    command.append("claude")
                result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True,
                                        text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                calls = [json.loads(line) for line in log.read_text().splitlines()]
                builds = [call for call in calls if call["args"][0] == "build"]
                self.assertEqual(len(builds), expected_builds)
                self.assertTrue(all(call["format"] == "docker" for call in builds), builds)


if __name__ == "__main__":
    unittest.main()
