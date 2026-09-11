"""Executable contracts for offline Fleet image builds; no daemon is required."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import os
import io
import tarfile


ROOT = Path(__file__).resolve().parents[1]
PIN = "sha256:" + "a" * 64


class FleetImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.bundle = self.work / "bundle"
        self.bundle.mkdir()
        wheel = "homericintelligence_hephaestus-1.0-py3-none-any.whl"
        data = b"unit-test dependency bytes; not an executable wheel"
        (self.bundle / wheel).write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        (self.bundle / "requirements.txt").write_text(
            f"HomericIntelligence-Hephaestus==1.0 --hash=sha256:{digest}\n"
        )
        self.manifest = {
            "schema": "hi/fleet-image-bundle/v1",
            "platform": "linux/arm64",
            "hephaestus_revision": "b" * 40,
            "files": {
                file.name: hashlib.sha256(file.read_bytes()).hexdigest()
                for file in self.bundle.iterdir()
            },
        }
        self.save_manifest()

    def save_manifest(self):
        (self.bundle / "bundle.json").write_text(json.dumps(self.manifest))

    def command(self, *extra, via_just=False):
        prefix = ["just", "fleet-image-plan"] if via_just else [
            sys.executable, "-m", "hephaestus.fleet_image", "plan"
        ]
        return subprocess.run(
            [*prefix,
             "--platform", "linux/arm64", "--bundle", str(self.bundle),
             "--node-base", "node@" + PIN,
             "--runtime-base", "fleet-toolchain@" + PIN,
             "--sbom-generator", "scanner@" + PIN,
             "--output", str(self.work / "output"), *extra],
            cwd=ROOT, capture_output=True, text=True,
        )

    def test_plan_exports_attested_oci_without_publish_or_credentials(self):
        result = self.command()
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        command = plan["command"]
        self.assertEqual(command[:3], ["docker", "buildx", "build"])
        self.assertIn("type=sbom,generator=scanner@" + PIN, command)
        self.assertIn("--provenance=mode=max", command)
        self.assertIn("hephaestus_bundle=" + str(self.bundle), command)
        self.assertTrue(any(value.startswith("type=oci,dest=") for value in command))
        self.assertNotIn("--push", command)
        self.assertNotIn("--load", command)
        self.assertIsNone(plan["image_digest"])
        self.assertFalse((self.work / "output").exists())

    def test_just_plan_preserves_paths_with_spaces(self):
        self.bundle = self.bundle.rename(self.work / "bundle inputs")
        output = self.work / "image output"
        result = self.command("--output", str(output), via_just=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertIn("hephaestus_bundle=" + str(self.bundle), plan["command"])
        self.assertIn("type=oci,dest=" + str(output / "image.oci.tar"), plan["command"])
        self.assertFalse(output.exists())

    def test_changed_dependency_is_rejected_before_build(self):
        (self.bundle / "requirements.txt").write_text("unexpected input")
        result = self.command()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("digest mismatch", result.stderr)

    def test_bundle_command_records_real_dependency_bytes(self):
        output = self.work / "prepared"
        result = subprocess.run(
            [sys.executable, "-m", "hephaestus.fleet_image", "bundle",
             "--platform", "linux/arm64", "--wheelhouse", str(self.bundle),
             "--requirements", str(self.bundle / "requirements.txt"),
             "--hephaestus-revision", "b" * 40, "--output", str(output)],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        recorded = json.loads((output / "bundle.json").read_text())
        self.assertEqual(recorded["files"], self.manifest["files"])
        self.assertEqual(recorded["platform"], "linux/arm64")

    def test_unlisted_credential_is_not_sent_to_builder(self):
        (self.bundle / "auth.json").write_text("private")
        result = self.command()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected bundle files", result.stderr)

    def test_wrong_architecture_and_mutable_base_are_rejected(self):
        for args in [("--platform", "linux/amd64"),
                     ("--node-base", "node:latest")]:
            with self.subTest(args=args):
                self.assertNotEqual(self.command(*args).returncode, 0)

    def test_remote_requirement_cannot_bypass_offline_contract(self):
        path = self.bundle / "requirements.txt"
        path.write_text("evil @ https://example.invalid/package.whl\n")
        self.manifest["files"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.save_manifest()
        result = self.command()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact package pin", result.stderr)

    def test_dependency_symlink_is_rejected(self):
        path = self.bundle / "requirements.txt"
        content = path.read_bytes()
        path.unlink()
        outside = self.work / "outside"
        outside.write_bytes(content)
        path.symlink_to(outside)
        result = self.command()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("regular file", result.stderr)

    def test_codex_image_contract_uses_pinned_noninteractive_flag(self):
        dockerfile = (ROOT / "vessels/codex/Dockerfile").read_text()
        self.assertIn("@openai/codex@0.153.4", dockerfile)
        self.assertNotIn("AGENT_HEADLESS_FLAG=--yes", dockerfile)

    def test_worker_entrypoint_dispatches_cli_and_rejects_version_drift(self):
        tools = self.work / "bin"
        tools.mkdir()
        for name, content in {
            "codex": '#!/bin/sh\nprintf "%s\\n" "$TEST_CODEX_VERSION"\n',
            "hephaestus-fleet-worker": '#!/bin/sh\nprintf "%s\\n" "$@"\n',
            "id": '#!/bin/sh\nprintf "%s\\n" "$TEST_UID"\n',
        }.items():
            path = tools / name
            path.write_text(content)
            path.chmod(0o755)
        env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"],
                   TEST_CODEX_VERSION="codex-cli 0.153.4", TEST_UID="1000")
        command = ["sh", str(ROOT / "vessels/fleet/entrypoint.sh"), "serve",
                   "--worker-id", "worker-1", "--capacity", "24"]
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), command[2:])
        env["TEST_CODEX_VERSION"] = "codex-cli 0.153.5"
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        env.update(TEST_CODEX_VERSION="codex-cli 0.153.4", TEST_UID="0")
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("non-root", result.stderr)

    def test_tool_archive_checksum_and_selected_binary_are_enforced(self):
        from hephaestus import fleet_image
        self.assertTrue(hasattr(fleet_image, "install_tool_archive"),
                        "Fleet tool installation must verify the archive before extraction")
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            binary = tarfile.TarInfo("just")
            binary.size = 6
            archive.addfile(binary, io.BytesIO(b"binary"))
            unrelated = tarfile.TarInfo("other")
            unrelated.size = 7
            archive.addfile(unrelated, io.BytesIO(b"ignored"))
        path = self.work / "just.tar.gz"
        path.write_bytes(stream.getvalue())
        output = self.work / "tools"
        output.mkdir()
        fleet_image.install_tool_archive(path, hashlib.sha256(path.read_bytes()).hexdigest(),
                                         "just", output)
        self.assertEqual((output / "just").read_bytes(), b"binary")
        self.assertEqual([file.name for file in output.iterdir()], ["just"])
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            fleet_image.install_tool_archive(path, "0" * 64, "just", output)

    def test_build_evidence_requires_sbom_and_provenance_bound_to_the_image(self):
        from hephaestus import fleet_image
        self.assertTrue(hasattr(fleet_image, "verify_export"),
                        "Build success must verify the exported attestations")

        def export(predicate_types, subject_override=None, damage_layer=False):
            blobs = {}

            def blob(data):
                encoded = json.dumps(data).encode()
                checksum = hashlib.sha256(encoded).hexdigest()
                blobs["blobs/sha256/" + checksum] = encoded
                return {"digest": "sha256:" + checksum, "size": len(encoded)}

            layer = blob({"test": "synthetic filesystem layer bytes"})
            layer["mediaType"] = "application/vnd.oci.image.layer.v1.tar+gzip"
            config = blob({"architecture": "arm64", "os": "linux"})
            image = blob({"schemaVersion": 2, "config": config, "layers": [layer]})
            statements = []
            for predicate in predicate_types:
                statement = blob({"_type": "https://in-toto.io/Statement/v0.1",
                                  "subject": [{"digest": {"sha256": subject_override or
                                                          image["digest"].split(":")[1]}}],
                                  "predicateType": predicate, "predicate": {}})
                statement["mediaType"] = "application/vnd.in-toto+json"
                statements.append(statement)
            attestation = blob({"schemaVersion": 2, "layers": statements})
            index = blob({"schemaVersion": 2, "manifests": [image, attestation]})
            blobs["index.json"] = json.dumps({"manifests": [index]}).encode()
            if damage_layer:
                blobs["blobs/sha256/" + layer["digest"].split(":")[1]] = b"corrupt layer"
            path = self.work / "image.oci.tar"
            with tarfile.open(path, "w") as archive:
                for name, data in blobs.items():
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
            return path, index["digest"]

        kinds = ["https://spdx.dev/Document", "https://slsa.dev/provenance/v1"]
        path, expected = export(kinds)
        evidence = fleet_image.verify_export(path, expected)
        self.assertEqual(set(evidence["predicate_types"]), set(kinds))
        for predicates, subject in [(kinds[:1], None), (kinds, "0" * 64)]:
            with self.subTest(predicates=predicates, subject=subject):
                path, expected = export(predicates, subject)
                with self.assertRaises(ValueError):
                    fleet_image.verify_export(path, expected)
        path, expected = export(kinds, damage_layer=True)
        with self.assertRaisesRegex(ValueError, "OCI blob"):
            fleet_image.verify_export(path, expected)


if __name__ == "__main__":
    unittest.main()
