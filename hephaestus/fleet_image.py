"""Validate Fleet image inputs and export OCI images with real attestations.

This module builds images. It does not provision workers or authorize tasks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
SOURCE_INPUTS = (
    "hephaestus/fleet_image.py", "vessels/fleet/Dockerfile",
    "vessels/fleet/Dockerfile.dockerignore", "vessels/fleet/entrypoint.sh",
    "vessels/fleet/package.json", "vessels/fleet/package-lock.json",
    "vessels/fleet/tool-artifacts.json",
)
PLATFORMS = ("linux/amd64", "linux/arm64")
PIN = re.compile(r"[^\s@]+@sha256:[0-9a-f]{64}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
REQUIREMENT = re.compile(
    r"[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?==[A-Za-z0-9_.+!-]+"
    r"(?:\s+--hash=sha256:[0-9a-f]{64})+\Z"
)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def install_tool_archive(archive: Path, expected: str, binary: str, output: Path) -> None:
    """Install only the named executable after verifying the complete archive."""
    if not HASH.fullmatch(expected) or digest(archive) != expected:
        raise ValueError("tool archive digest mismatch")
    if binary not in ("just", "pixi"):
        raise ValueError("unsupported tool")
    with tarfile.open(archive, "r:gz") as source:
        entry = source.getmember(binary)
        if not entry.isfile():
            raise ValueError("tool archive executable must be a regular file")
        stream = source.extractfile(entry)
        if stream is None:
            raise ValueError("tool archive executable is missing")
        destination = output / binary
        if destination.is_symlink():
            raise ValueError("tool destination cannot be a symlink")
        with destination.open("wb") as target:
            while chunk := stream.read(1024 * 1024):
                target.write(chunk)
        destination.chmod(0o755)


def install_tools(argv: list[str]) -> int:
    arguments = argparse.ArgumentParser(description="Install pinned Fleet image tools")
    arguments.add_argument("--platform", choices=PLATFORMS, required=True)
    arguments.add_argument("--artifacts", type=Path, required=True)
    arguments.add_argument("--destination", type=Path, required=True)
    args = arguments.parse_args(argv)
    artifacts = json.loads(args.artifacts.read_text())
    for name in ("just", "pixi"):
        artifact = artifacts[name][args.platform]
        if not artifact["url"].startswith("https://github.com/"):
            raise ValueError("tool URL must use the recorded HTTPS release source")
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "tool.tar.gz"
            with urllib.request.urlopen(artifact["url"], timeout=120) as response:
                with archive.open("wb") as target:
                    while chunk := response.read(1024 * 1024):
                        target.write(chunk)
            install_tool_archive(archive, artifact["sha256"], name, args.destination)
    return 0


def verify_export(path: Path, expected_digest: str) -> dict:
    """Check OCI content hashes and required attestations against image subjects.

    This establishes content binding, not a signature or SLSA certification.
    """
    found: set[str] = set()
    image_subjects: set[str] = set()
    image_configs: dict[str, str] = {}
    statements: list[dict] = []
    with tarfile.open(path, "r") as archive:
        def verify_blob(descriptor: dict) -> None:
            identifier = descriptor.get("digest", "")
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", identifier):
                raise ValueError("OCI blob requires a SHA256 digest")
            checksum = identifier.split(":")[1]
            try:
                member = archive.getmember("blobs/sha256/" + checksum)
            except KeyError as error:
                raise ValueError("OCI blob is missing") from error
            if not member.isfile() or member.size != descriptor.get("size"):
                raise ValueError("OCI blob must be a regular file of the declared size")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("OCI blob is unreadable")
            with stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != checksum:
                    raise ValueError("OCI blob digest mismatch")

        def read_json(name: str, checksum: str | None = None) -> dict:
            member = archive.getmember(name)
            if not member.isfile():
                raise ValueError("OCI metadata must be a regular file")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("OCI metadata is missing")
            content = stream.read()
            if checksum and hashlib.sha256(content).hexdigest() != checksum:
                raise ValueError("OCI metadata digest mismatch")
            return json.loads(content)

        def visit(descriptor: dict) -> None:
            identifier = descriptor.get("digest", "")
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", identifier):
                raise ValueError("OCI descriptor requires a SHA256 digest")
            if identifier in found:
                return
            found.add(identifier)
            checksum = identifier.split(":")[1]
            document = read_json("blobs/sha256/" + checksum, checksum)
            if "manifests" in document:
                for child in document["manifests"]:
                    visit(child)
            elif "layers" in document:
                if "config" in document:
                    verify_blob(document["config"])
                attested = False
                for layer in document["layers"]:
                    if layer.get("mediaType") == "application/vnd.in-toto+json":
                        attested = True
                        visit(layer)
                    else:
                        verify_blob(layer)
                if not attested:
                    image_subjects.add(checksum)
                    image_configs[checksum] = document["config"]["digest"]
            elif "predicateType" in document:
                statements.append(document)

        roots = read_json("index.json").get("manifests", [])
        if len(roots) != 1 or roots[0].get("digest") != expected_digest:
            raise ValueError("BuildKit digest must identify the single exported OCI output root")
        visit(roots[0])
    predicate_types: set[str] = set()
    covered: dict[str, set[str]] = {subject: set() for subject in image_subjects}
    for statement in statements:
        predicate = statement["predicateType"]
        for subject in statement.get("subject", []):
            checksum = subject.get("digest", {}).get("sha256")
            if checksum not in image_subjects:
                raise ValueError("attestation subject does not match an exported image")
            covered[checksum].add(predicate)
            predicate_types.add(predicate)
    if not covered or any("https://spdx.dev/Document" not in kinds or
                          not any(kind.startswith("https://slsa.dev/provenance/") for kind in kinds)
                          for kinds in covered.values()):
        raise ValueError("each exported image requires an SPDX SBOM and provenance attestation")
    return {"predicate_types": sorted(predicate_types), "image_subjects": sorted(image_subjects),
            "image_configs": image_configs}


def validate_bundle(path: Path, platform: str) -> dict:
    """Require a closed, hash-locked wheel context with explicit source provenance."""
    manifest_path = path / "bundle.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("bundle.json must be a regular file")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") != "hi/fleet-image-bundle/v1":
        raise ValueError("unsupported bundle schema")
    if manifest.get("platform") != platform:
        raise ValueError("bundle platform does not match the requested image")
    if not re.fullmatch(r"[0-9a-f]{40}", manifest.get("hephaestus_revision", "")):
        raise ValueError("the bundle requires a full Hephaestus source revision")
    files = manifest.get("files", {})
    if not isinstance(files, dict) or "requirements.txt" not in files:
        raise ValueError("the bundle requires a hashed requirements.txt")
    if set(child.name for child in path.iterdir()) != set(files) | {"bundle.json"}:
        raise ValueError("unexpected bundle files; supply only the declared wheel bundle")
    for name, expected in files.items():
        if Path(name).name != name or not (name.endswith(".whl") or name == "requirements.txt"):
            raise ValueError("bundle entries must be wheel filenames or requirements.txt")
        artifact = path / name
        if artifact.is_symlink() or not artifact.is_file():
            raise ValueError(f"bundle entry must be a regular file: {name}")
        if not isinstance(expected, str) or not HASH.fullmatch(expected) or digest(artifact) != expected:
            raise ValueError(f"bundle digest mismatch: {name}")
    requirements = [line.strip() for line in (path / "requirements.txt").read_text().splitlines()
                    if line.strip() and not line.lstrip().startswith("#")]
    if not requirements or any(not REQUIREMENT.fullmatch(line) for line in requirements):
        raise ValueError("each requirement needs an exact package pin and SHA256 hash on one line")
    if not any(re.match(r"homericintelligence[-_]hephaestus(?:\[|==)", line, re.I)
               for line in requirements):
        raise ValueError("requirements.txt must include the built Hephaestus wheel")
    wheel_hashes = {value for name, value in files.items() if name.endswith(".whl")}
    requested_hashes = set(re.findall(r"--hash=sha256:([0-9a-f]{64})", "\n".join(requirements)))
    if not wheel_hashes or not requested_hashes.issubset(wheel_hashes):
        raise ValueError("every requirement hash must identify a supplied wheel")
    return manifest


def prepare_bundle(argv: list[str]) -> int:
    arguments = argparse.ArgumentParser(description="Hash an existing offline wheel bundle")
    arguments.add_argument("--platform", choices=PLATFORMS, required=True)
    arguments.add_argument("--wheelhouse", type=Path, required=True)
    arguments.add_argument("--requirements", type=Path, required=True)
    arguments.add_argument("--hephaestus-revision", required=True,
                           help="source commit recorded by the wheel build; does not attest source provenance")
    arguments.add_argument("--output", type=Path, required=True)
    args = arguments.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", args.hephaestus_revision):
        arguments.error("--hephaestus-revision requires a full commit identifier")
    if args.output.exists():
        arguments.error("the output directory must not exist")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.output.parent) as directory:
        staged = Path(directory)
        inputs = [(args.requirements, "requirements.txt")]
        inputs.extend((wheel, wheel.name) for wheel in sorted(args.wheelhouse.glob("*.whl")))
        for source, name in inputs:
            if source.is_symlink() or not source.is_file():
                arguments.error(f"bundle input must be a regular file: {source}")
            shutil.copyfile(source, staged / name)
        manifest = {"schema": "hi/fleet-image-bundle/v1", "platform": args.platform,
                    "hephaestus_revision": args.hephaestus_revision,
                    "files": {path.name: digest(path) for path in staged.iterdir()}}
        (staged / "bundle.json").write_text(json.dumps(manifest, indent=2) + "\n")
        validate_bundle(staged, args.platform)
        # Atomic publication keeps partially validated contexts out of builds.
        staged.rename(args.output)
    print(json.dumps(manifest, indent=2))
    return 0


def image_plan(args: argparse.Namespace) -> dict:
    bundle = args.bundle.absolute()
    manifest = validate_bundle(bundle, args.platform)
    for image in (args.node_base, args.runtime_base, args.sbom_generator):
        if not PIN.fullmatch(image):
            raise ValueError("base images and the SBOM generator require a registry reference with sha256 digest")
    output = args.output.absolute()
    command = [
        "docker", "buildx", "build", "--platform", args.platform,
        "--file", str(ROOT / "vessels/fleet/Dockerfile"),
        "--target", args.target,
        "--build-context", f"hephaestus_bundle={bundle}",
        "--build-arg", f"NODE_BASE_IMAGE={args.node_base}",
        "--build-arg", f"RUNTIME_BASE_IMAGE={args.runtime_base}",
        "--build-arg", f"HEPHAESTUS_REVISION={manifest['hephaestus_revision']}",
        "--attest", f"type=sbom,generator={args.sbom_generator}",
        "--provenance=mode=max",
        "--metadata-file", str(output / "buildkit-metadata.json"),
        "--output", f"type=oci,dest={output / 'image.oci.tar'}",
        str(ROOT),
    ]
    return {"schema": "hi/fleet-image-build/v1", "platform": args.platform,
            "target": args.target, "command": command, "image_digest": None,
            "source_files": {name: digest(ROOT / name) for name in SOURCE_INPUTS},
            "bundle_digest": digest(bundle / "bundle.json"),
            "hephaestus_revision": manifest["hephaestus_revision"],
            "source_revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "source_dirty": bool(subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("action", choices=("plan", "build"))
    result.add_argument("--platform", choices=PLATFORMS, required=True)
    result.add_argument("--bundle", type=Path, required=True)
    result.add_argument("--node-base", required=True)
    result.add_argument("--runtime-base", required=True)
    result.add_argument("--sbom-generator", required=True)
    result.add_argument("--target", choices=("worker", "build-tools"), default="worker")
    result.add_argument("--output", type=Path, required=True)
    return result


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "install-tools":
        return install_tools(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "bundle":
        return prepare_bundle(sys.argv[2:])
    arguments = parser()
    args = arguments.parse_args()
    try:
        plan = image_plan(args)
        if args.action == "build":
            # Each run gets a new directory; stale metadata cannot count as this build.
            args.output.mkdir(parents=True, exist_ok=False)
            # Freeze only declared build inputs. Never send a checkout or home wholesale.
            source_context = args.output.absolute() / "source"
            for name, expected in plan["source_files"].items():
                target = source_context / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
                if digest(target) != expected:
                    raise ValueError("source changed while preparing the image build")
            bundle_context = args.output.absolute() / "bundle"
            bundle_context.mkdir()
            original_manifest = validate_bundle(args.bundle, args.platform)
            for name in [*original_manifest["files"], "bundle.json"]:
                shutil.copyfile(args.bundle / name, bundle_context / name)
            validate_bundle(bundle_context, args.platform)
            if digest(bundle_context / "bundle.json") != plan["bundle_digest"]:
                raise ValueError("bundle changed while preparing the image build")
            plan["command"] = [
                str(source_context / "vessels/fleet/Dockerfile")
                if value == str(ROOT / "vessels/fleet/Dockerfile")
                else f"hephaestus_bundle={bundle_context}"
                if value.startswith("hephaestus_bundle=")
                else value for value in plan["command"]
            ]
            plan["command"][-1] = str(source_context)
            (args.output / "build-inputs.json").write_text(json.dumps(plan, indent=2) + "\n")
            subprocess.run(plan["command"], check=True)
            metadata = json.loads((args.output / "buildkit-metadata.json").read_text())
            image_digest = metadata.get("containerimage.digest", "")
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest):
                raise ValueError("BuildKit did not return an image manifest digest")
            # Preserve BuildKit's raw metadata/OCI attestations. No publication is implied.
            plan["attestations"] = verify_export(args.output / "image.oci.tar", image_digest)
            plan["image_digest"] = image_digest
            plan["oci_archive_sha256"] = digest(args.output / "image.oci.tar")
            (args.output / "build-result.json").write_text(json.dumps(plan, indent=2) + "\n")
        print(json.dumps(plan, indent=2))
        return 0
    except (ValueError, OSError, KeyError, tarfile.TarError, subprocess.CalledProcessError) as error:
        arguments.exit(1, f"Fleet image: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
