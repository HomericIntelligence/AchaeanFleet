"""Build and smoke-test pinned Fleet image artifacts without publishing them."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform as host_platform
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import zipfile

from .fleet_image import PLATFORMS, ROOT, digest, prepare_bundle, verify_export


INPUTS = ROOT / "vessels/fleet/ci/inputs.json"


def runtime_command(engine: str, image: str, target: str, output: Path, token: str) -> list[str]:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image) or not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ValueError("runtime smoke requires an immutable image and fresh ownership token")
    if target not in ("worker", "build-tools"):
        raise ValueError("unsupported runtime target")
    return [engine, "create", "--pull=never", "--name=fleet-ci-" + token,
            "--label=hi.fleet.image-ci=" + token, "--network=none", "--read-only",
            "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=1000:1000",
            "--userns=keep-id:uid=1000,gid=1000", "--cpus=1", "--memory=1g",
            "--memory-swap=1g", "--pids-limit=128", "--http-proxy=false",
            "--tmpfs=/tmp:rw,nosuid,nodev,size=67108864", "--workdir=/workspace",
            "--env=HOME=/var/lib/fleet/home", "--env=CODEX_HOME=/var/lib/fleet/codex",
            f"--mount=type=bind,src={output / 'state'},dst=/var/lib/fleet,relabel=private",
            f"--mount=type=bind,src={output / 'workspace'},dst=/workspace,relabel=private",
            f"--mount=type=bind,src={output / 'runtime_probe.py'},dst=/opt/runtime_probe.py,ro,relabel=private",
            "--entrypoint=/opt/fleet/bin/python", image, "/opt/runtime_probe.py", target]


def smoke(platform: str, target: str, image_output: Path, *, engine: str) -> dict:
    """Load only verified OCI bytes and run a bounded disposable packaging check."""
    build = json.loads((image_output / "build-result.json").read_text())
    archive = image_output / "image.oci.tar"
    if build.get("platform") != platform or build.get("target") != target or digest(archive) != build.get("oci_archive_sha256"):
        raise ValueError("runtime smoke image does not match its actual build record")
    verified = verify_export(archive, build["image_digest"])
    configs = list(verified["image_configs"].values())
    if len(configs) != 1:
        raise ValueError("native runtime smoke requires exactly one image config")
    image = configs[0]
    output = image_output / "runtime-smoke"
    output.mkdir(mode=0o700, exist_ok=False)
    for name in ("state", "workspace"):
        (output / name).mkdir(mode=0o700)
    shutil.copyfile(INPUTS.parent / "runtime_probe.py", output / "runtime_probe.py")
    env = dict(os.environ)
    captured([engine, "load", "--input", str(archive)], output / "load", cwd=ROOT, env=env)
    captured([engine, "image", "inspect", image], output / "image-inspect", cwd=ROOT, env=env)
    inspection = json.loads((output / "image-inspect.stdout").read_text())[0]
    if inspection.get("Id", "").removeprefix("sha256:") != image.removeprefix("sha256:"):
        raise ValueError("loaded runtime image identity mismatch")
    if inspection.get("Os") != "linux" or inspection.get("Architecture") != platform.split("/")[1]:
        raise ValueError("loaded runtime platform mismatch")
    expected_entrypoint = ["/opt/fleet-entrypoint.sh"] if target == "worker" else ["just"]
    config = inspection.get("Config", {})
    if config.get("User") != "1000:1000" or config.get("Entrypoint") != expected_entrypoint:
        raise ValueError("loaded runtime user/entrypoint mismatch")
    token = secrets.token_hex(16)
    command = runtime_command(engine, image, target, output, token)
    (output / "ownership.json").write_text(json.dumps({
        "name": "fleet-ci-" + token, "label": token, "image": image,
        "probeSha256": digest(output / "runtime_probe.py"), "command": command}, indent=2) + "\n")
    cid = None
    try:
        captured(command, output / "create", cwd=ROOT, env=env, timeout=30)
        cid = (output / "create.stdout").read_text().strip()
        if not re.fullmatch(r"[0-9a-f]{64}", cid):
            raise ValueError("engine did not return a full container identity")
        captured([engine, "inspect", cid], output / "container-before", cwd=ROOT, env=env, timeout=30)
        created = json.loads((output / "container-before.stdout").read_text())[0]
        policy = created.get("HostConfig", {})
        if (policy.get("Memory") != 1073741824 or policy.get("CpuPeriod") != 100000 or
                policy.get("CpuQuota") != 100000 or policy.get("PidsLimit") != 128 or
                policy.get("ReadonlyRootfs") is not True or policy.get("NetworkMode") != "none"):
            raise ValueError("runtime resource/filesystem/network policy mismatch")
        captured([engine, "start", "--attach", cid], output / "probe", cwd=ROOT, env=env, timeout=90)
        captured([engine, "inspect", cid], output / "container-after", cwd=ROOT, env=env, timeout=30)
        state = json.loads((output / "container-after.stdout").read_text())[0]["State"]
        if state.get("Running") is not False or state.get("ExitCode") != 0:
            raise ValueError("runtime smoke did not exit successfully")
        result = json.loads((output / "probe.stdout").read_text())
        if result.get("passed") is not True or result.get("target") != target:
            raise ValueError("runtime smoke returned no successful observation")
    finally:
        # The random name was persisted before create, including when create timed out.
        # Adopt it for cleanup only after the exact label and pinned image agree.
        identifier = cid if cid and re.fullmatch(r"[0-9a-f]{64}", cid) else "fleet-ci-" + token
        try:
            captured([engine, "inspect", identifier], output / "cleanup-inspect", cwd=ROOT, env=env, timeout=30)
        except subprocess.CalledProcessError:
            # A failed inspect is uncertainty, never evidence that cleanup succeeded.
            raise RuntimeError("runtime cleanup inventory unavailable; reconcile ownership.json") from None
        item = json.loads((output / "cleanup-inspect.stdout").read_text())[0]
        owned_cid = item.get("Id", "")
        if not re.fullmatch(r"[0-9a-f]{64}", owned_cid) or item.get("Config", {}).get("Labels", {}).get("hi.fleet.image-ci") != token:
            raise ValueError("runtime cleanup ownership mismatch")
        if item.get("Image", "").removeprefix("sha256:") != image.removeprefix("sha256:"):
            raise ValueError("runtime cleanup image mismatch")
        captured([engine, "rm", "--force", owned_cid], output / "remove", cwd=ROOT, env=env, timeout=30)
        captured([engine, "ps", "--all", "--no-trunc", "--quiet", "--filter", "id=" + owned_cid],
                 output / "absence", cwd=ROOT, env=env, timeout=30)
        if (output / "absence.stdout").read_text().strip():
            raise ValueError("runtime smoke container remains after removal")
    record = {"imageConfigDigest": image, "ociArchiveSha256": digest(archive),
              "observations": result, "containerRemoved": True, "authorizesAdmission": False}
    (output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def captured(argv: list[str], output: Path, *, cwd: Path, env: dict[str, str], timeout: int = 300) -> None:
    """Retain actual command output, including timeout failures, before propagating errors."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".invocation.json").write_text(json.dumps({
        "argv": argv, "cwd": str(cwd), "timeoutSeconds": timeout}, indent=2) + "\n")
    with output.with_suffix(".stdout").open("wb") as stdout, output.with_suffix(".stderr").open("wb") as stderr:
        try:
            result = subprocess.run(argv, cwd=cwd, env=env, stdout=stdout, stderr=stderr, timeout=timeout)
        except subprocess.TimeoutExpired:
            output.with_suffix(".result.json").write_text('{"timeout": true}\n')
            raise
    output.with_suffix(".result.json").write_text(json.dumps({"exitCode": result.returncode}) + "\n")
    result.check_returncode()


def prepare(platform: str, source: Path, output: Path) -> dict:
    """Build the actual pinned source wheel and a closed target-platform wheel bundle."""
    if sys.version_info[:2] != (3, 13):
        raise ValueError("Fleet wheel preparation requires Python 3.13")
    inputs = json.loads(INPUTS.read_text())
    revision = inputs["hephaestusRevision"]
    source_record = freeze_source(source, revision, output)
    home = output / "private-home"
    home.mkdir(mode=0o700)
    env = {"PATH": os.defpath, "HOME": str(home), "LANG": "C.UTF-8",
           "PIP_CONFIG_FILE": os.devnull, "PIP_DISABLE_PIP_VERSION_CHECK": "1",
           "PIP_NO_INPUT": "1", "PYTHONNOUSERSITE": "1"}
    environment = output / "build-environment"
    captured([sys.executable, "-m", "venv", str(environment)], output / "logs/venv", cwd=ROOT, env=env)
    python = str(environment / "bin/python")
    common = [python, "-m", "pip", "--isolated", "--disable-pip-version-check"]
    captured([*common, "install", "--no-cache-dir", "--index-url", "https://pypi.org/simple",
              "--require-hashes", "--only-binary=:all:", "-r", str(INPUTS.parent / "build-requirements.txt")],
             output / "logs/build-dependencies", cwd=ROOT, env=env)
    version = "0.1.dev1+g" + revision[:9] + ".fleet"
    env["SETUPTOOLS_SCM_PRETEND_VERSION"] = version
    env["SOURCE_DATE_EPOCH"] = subprocess.check_output(
        ["git", "show", "-s", "--format=%ct", revision], cwd=source, text=True).strip()
    dist = output / "dist"
    captured([python, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(dist)],
             output / "logs/wheel-build", cwd=output / "source", env=env)
    wheels = list(dist.glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError("Hephaestus build must produce exactly one wheel")
    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ValueError("built wheel metadata is ambiguous")
        metadata = archive.read(metadata_names[0]).decode()
        if f"\nVersion: {version}\n" not in metadata or "\nName: HomericIntelligence-Hephaestus\n" not in metadata:
            raise ValueError("built wheel metadata does not match the selected source package/version")
    wheelhouse = output / "wheelhouse"
    wheelhouse.mkdir()
    architecture = platform.split("/")[1]
    machine = {"amd64": "x86_64", "arm64": "aarch64"}[architecture]
    runtime_lock = INPUTS.parent / f"runtime-{architecture}.txt"
    captured([*common, "download", "--no-cache-dir", "--index-url", "https://pypi.org/simple",
              "--require-hashes", "--only-binary=:all:", "--no-deps", "--python-version", "3.13",
              "--implementation", "cp", "--abi", "cp313",
              "--platform", "manylinux_2_28_" + machine, "--platform", "manylinux_2_17_" + machine,
              "--dest", str(wheelhouse), "-r", str(runtime_lock)],
             output / "logs/runtime-dependencies", cwd=ROOT, env=env)
    shutil.copyfile(wheel, wheelhouse / wheel.name)
    requirements = output / "requirements.txt"
    requirements.write_text(runtime_lock.read_text().rstrip() + "\n" +
                            f"homericintelligence-hephaestus[automation]=={version} --hash=sha256:{digest(wheel)}\n")
    prepare_bundle(["--platform", platform, "--wheelhouse", str(wheelhouse),
                    "--requirements", str(requirements), "--hephaestus-revision", revision,
                    "--output", str(output / "bundle")])
    result = {"schema": "hi/fleet-ci-preparation/v1", "platform": platform,
              "hephaestusRevision": revision, "sourceArchiveSha256": source_record["archiveSha256"],
              "wheel": wheel.name, "wheelSha256": digest(wheel), "version": version,
              "inputsSha256": digest(INPUTS), "runtimeLockSha256": digest(runtime_lock),
              "buildLockSha256": digest(INPUTS.parent / "build-requirements.txt"),
              "bundleManifestSha256": digest(output / "bundle/bundle.json")}
    (output / "prepare-result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def freeze_source(source: Path, revision: str, output: Path) -> dict:
    """Copy only the named commit, independently of working-tree/private files."""
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Hephaestus source requires an immutable commit")
    actual = subprocess.check_output(
        ["git", "rev-parse", "--verify", revision + "^{commit}"], cwd=source, text=True).strip()
    if actual != revision:
        raise ValueError("Hephaestus source revision mismatch")
    archive = subprocess.check_output(["git", "archive", "--format=tar", revision], cwd=source)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    (output / "source.tar").write_bytes(archive)
    destination = output / "source"
    destination.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        stream.extractall(destination, filter="data")
    files = {}
    for path in sorted(destination.rglob("*")):
        if path.is_symlink():
            files[str(path.relative_to(destination))] = {"symlink": str(path.readlink())}
        elif path.is_file():
            files[str(path.relative_to(destination))] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    record = {"revision": revision, "archiveSha256": hashlib.sha256(archive).hexdigest(), "files": files}
    (output / "source-manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def image_plan(platform: str, source: Path, output: Path) -> dict:
    inputs = json.loads(INPUTS.read_text())
    bases = inputs["bases"][platform.split("/")[1]]
    images = []
    for target in ("worker", "build-tools"):
        images.append({"target": target, "argv": [
            sys.executable, "-m", "hephaestus.fleet_image", "build",
            "--platform", platform, "--target", target,
            "--bundle", str(output / "bundle"),
            "--node-base", bases["node"], "--runtime-base", bases["python"],
            "--sbom-generator", bases["sbom"],
            "--output", str(output / target),
        ]})
    return {"schema": "hi/fleet-ci/v1", "platform": platform,
            "hephaestusRevision": inputs["hephaestusRevision"],
            "source": str(source), "output": str(output), "images": images}


def build_and_smoke(platform: str, source: Path, output: Path, engine: str) -> dict:
    expected_machine = {"linux/amd64": "x86_64", "linux/arm64": "aarch64"}[platform]
    if sys.platform != "linux" or host_platform.machine() != expected_machine:
        raise ValueError("Fleet runtime CI requires a native Linux runner for the selected platform")
    prepared = json.loads((output / "prepare-result.json").read_text())
    inputs = json.loads(INPUTS.read_text())
    if prepared.get("inputsSha256") != digest(INPUTS) or prepared.get("platform") != platform:
        raise ValueError("prepared bundle no longer matches the selected CI inputs")
    if prepared.get("bundleManifestSha256") != digest(output / "bundle/bundle.json"):
        raise ValueError("prepared bundle manifest changed")
    if prepared.get("hephaestusRevision") != inputs["hephaestusRevision"]:
        raise ValueError("prepared source revision changed")
    result = {"schema": "hi/fleet-ci-result/v1", "platform": platform,
              "hephaestusRevision": inputs["hephaestusRevision"], "images": []}
    for image in image_plan(platform, source, output)["images"]:
        captured(image["argv"], output / "logs" / ("image-" + image["target"]),
                 cwd=ROOT, env=dict(os.environ), timeout=1800)
        result["images"].append(smoke(platform, image["target"], output / image["target"], engine=engine))
    (output / "ci-result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "prepare", "build", "run"))
    parser.add_argument("--platform", choices=PLATFORMS, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--engine", default="podman", help="Podman executable for isolated runtime checks")
    args = parser.parse_args()
    source, output = args.source.absolute(), args.output.absolute()
    if args.action == "plan":
        result = image_plan(args.platform, source, output)
    elif args.action == "prepare":
        result = prepare(args.platform, source, output)
    else:
        engine = shutil.which(args.engine)
        if engine is None:
            parser.error("the runtime Podman executable is unavailable")
        if args.action == "run":
            prepare(args.platform, source, output)
        result = build_and_smoke(args.platform, source, output, engine)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
