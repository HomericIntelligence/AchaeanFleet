"""Fleet's non-publishing CI entrypoint must cover both shipped targets."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FleetCITests(unittest.TestCase):
    def test_just_recipe_preserves_paths_with_spaces(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new output"
            result = subprocess.run([shutil.which("just"), "fleet-ci", "plan", "--platform", "linux/arm64",
                                     "--source", "/explicit/source checkout", "--output", str(output)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["output"], str(output))
            self.assertFalse(output.exists())

    def test_runtime_plan_is_pinned_bounded_and_mounts_only_private_test_inputs(self):
        from hephaestus import fleet_ci

        self.assertTrue(hasattr(fleet_ci, "runtime_command"), "dedicated CI must exercise the built image")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            argv = fleet_ci.runtime_command("/usr/bin/podman", "sha256:" + "a" * 64,
                                            "worker", root, "b" * 32)
            for flag in ("--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                         "--cpus=1", "--memory=1g", "--pids-limit=128", "--pull=never", "--user=1000:1000"):
                self.assertIn(flag, argv)
            mounts = [item for item in argv if item.startswith("--mount=")]
            self.assertEqual(len(mounts), 3)
            self.assertTrue(all(str(root) in item for item in mounts))
            self.assertFalse(any("docker.sock" in item or "podman.sock" in item for item in argv))
            with self.assertRaises(ValueError):
                fleet_ci.runtime_command("/usr/bin/podman", "worker:latest", "worker", root, "b" * 32)

    def test_command_failure_preserves_actual_output_and_status(self):
        from hephaestus.fleet_ci import captured

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(subprocess.CalledProcessError):
                captured([sys.executable, "-c", "import sys; print('before failure'); sys.exit(7)"],
                         root / "probe", cwd=root, env={"PATH": os.defpath})
            self.assertEqual((root / "probe.stdout").read_text(), "before failure\n")
            self.assertEqual(json.loads((root / "probe.result.json").read_text()), {"exitCode": 7})

    def test_source_snapshot_uses_only_the_exact_git_revision(self):
        from hephaestus import fleet_ci

        self.assertTrue(hasattr(fleet_ci, "freeze_source"), "CI must bind its wheel to actual Git source bytes")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
            (repo / "package.py").write_text("original = True\n")
            subprocess.run(["git", "add", "package.py"], cwd=repo, check=True)
            tree = subprocess.check_output(["git", "write-tree"], cwd=repo, text=True).strip()
            env = dict(os.environ, GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
                       GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid")
            revision = subprocess.check_output(["git", "commit-tree", tree], input="fixture\n",
                                               cwd=repo, env=env, text=True).strip()
            (repo / "package.py").write_text("uncommitted = True\n")
            (repo / "auth.json").write_text("synthetic private file")
            output = root / "frozen"
            record = fleet_ci.freeze_source(repo, revision, output)
            self.assertEqual((output / "source/package.py").read_text(), "original = True\n")
            self.assertFalse((output / "source/auth.json").exists())
            self.assertEqual(record["revision"], revision)
            self.assertEqual(set(record["files"]), {"package.py"})
            with self.assertRaises(ValueError):
                fleet_ci.freeze_source(repo, "main", root / "mutable")

    def test_plan_covers_both_targets_without_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new output"
            result = subprocess.run(
                [sys.executable, "-m", "hephaestus.fleet_ci", "plan",
                 "--platform", "linux/arm64", "--source", "/explicit/source",
                 "--output", str(output)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual({item["target"] for item in plan["images"]}, {"worker", "build-tools"})
            for item in plan["images"]:
                self.assertIn("build", item["argv"])
                self.assertIn("--sbom-generator", item["argv"])
                self.assertNotIn("--push", item["argv"])
                self.assertNotIn("--load", item["argv"])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
