"""Exercise workspace preparation with a real dependency and an offline uv cache."""

from __future__ import annotations

import base64
import csv
import functools
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import zipfile

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "vessels" / "athena-tools" / "prepare_workspace.py"
DEPENDENCY_FILES = ("pyproject.toml", "uv.lock", ".python-version")
SNAPSHOT_SHA256 = "a" * 64
IMAGE_DIGEST = "sha256:" + "b" * 64
UPSTREAM_REVISION = "c" * 40


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cache_sha256(root: Path) -> str:
    """Hash logical files, including files reached through internal uv links."""
    files = []
    for directory, _, names in os.walk(root, followlinks=True):
        for name in names:
            path = Path(directory) / name
            assert path.resolve().is_relative_to(root.resolve())
            files.append([path.relative_to(root).as_posix(), _sha256(path)])
    return hashlib.sha256(
        json.dumps(sorted(files), separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _environment(home: Path, uv: str) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    return {
        "PATH": os.pathsep.join((str(Path(uv).parent), str(Path(sys.executable).parent), "/usr/bin", "/bin")),
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / "config"),
        "UV_PYTHON": sys.executable,
        "UV_PYTHON_DOWNLOADS": "never",
        "UV_LINK_MODE": "copy",
        "NO_PROXY": "127.0.0.1,localhost",
    }


def _run(args: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, timeout=30)


def _wheel(path: Path) -> None:
    """Create a valid wheel without a build backend or external downloads."""
    metadata = "fleet_offline_fixture-1.0.0.dist-info"
    entries = {
        "fleet_offline_fixture.py": b"VALUE = 'installed-from-seed'\n",
        f"{metadata}/METADATA": b"Metadata-Version: 2.1\nName: fleet-offline-fixture\nVersion: 1.0.0\n",
        f"{metadata}/WHEEL": b"Wheel-Version: 1.0\nGenerator: fleet-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    records = io.StringIO()
    writer = csv.writer(records, lineterminator="\n")
    for name, contents in entries.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(contents).digest()).rstrip(b"=").decode()
        writer.writerow((name, f"sha256={digest}", len(contents)))
    writer.writerow((f"{metadata}/RECORD", "", ""))
    entries[f"{metadata}/RECORD"] = records.getvalue().encode()
    with zipfile.ZipFile(path, "w") as archive:
        for name, contents in entries.items():
            archive.writestr(name, contents)


@pytest.fixture(scope="module")
def offline_project(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, str]:
    uv = shutil.which("uv")
    assert uv is not None, "These behavioral tests require uv on PATH."
    root = tmp_path_factory.mktemp("offline-fixture")
    project = root / "project"
    project.mkdir()
    seed = root / "seed"
    index = root / "index"
    package = index / "simple" / "fleet-offline-fixture"
    package.mkdir(parents=True)
    wheel = package / "fleet_offline_fixture-1.0.0-py3-none-any.whl"
    _wheel(wheel)
    (package / "index.html").write_text(f'<a href="{wheel.name}#sha256={_sha256(wheel)}">fixture</a>\n')

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:
            pass

    handler = functools.partial(Handler, directory=str(index))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        (project / "pyproject.toml").write_text(
            '[project]\nname = "offline-consumer"\nversion = "1.0.0"\n'
            'requires-python = ">=3.13,<3.14"\ndependencies = ["fleet-offline-fixture==1.0.0"]\n'
            '[[tool.uv.index]]\nname = "fixture"\ndefault = true\n'
            f'url = "http://127.0.0.1:{server.server_port}/simple"\n'
        )
        (project / ".python-version").write_text(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}\n")
        env = _environment(root / "home", uv)
        result = _run([uv, "sync", "--cache-dir", str(seed), "--python", sys.executable], cwd=project, env=env)
        assert result.returncode == 0, result.stdout + result.stderr
        imported = _run(
            [str(project / ".venv" / "bin" / "python"), "-I", "-c", "import fleet_offline_fixture; print(fleet_offline_fixture.VALUE)"],
            cwd=project, env=env,
        )
        assert imported.returncode == 0, imported.stderr
        assert imported.stdout.strip() == "installed-from-seed"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    shutil.rmtree(index)
    shutil.rmtree(project / ".venv")
    assert not index.exists()
    assert not thread.is_alive()
    return project, seed, uv


def _inputs(tmp_path: Path, offline_project: tuple[Path, Path, str]) -> tuple[Path, Path, Path, dict[str, str]]:
    project, source_seed, uv = offline_project
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for name in DEPENDENCY_FILES:
        shutil.copyfile(project / name, workspace / name)
    seed = tmp_path / "seed"
    shutil.copytree(source_seed, seed)
    binding = tmp_path / "binding.json"
    _write_binding(workspace, seed, binding)
    env = _environment(tmp_path / "home", uv)
    env["XDG_CACHE_HOME"] = str(workspace / ".fleet-runtime" / "xdg" / "cache")
    return workspace, seed, binding, env


def _write_binding(workspace: Path, seed: Path, binding: Path) -> None:
    binding.write_text(json.dumps({
        "dependency_files": {name: _sha256(workspace / name) for name in DEPENDENCY_FILES},
        "cache_sha256": _cache_sha256(seed),
        "upstream_revision": UPSTREAM_REVISION,
    }))


def _prepare(workspace: Path, seed: Path, binding: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return _run([
        sys.executable, str(PREPARE), "--workspace", str(workspace), "--seed", str(seed),
        "--binding", str(binding), "--snapshot-sha256", SNAPSHOT_SHA256,
        "--image-digest", IMAGE_DIGEST,
    ], cwd=workspace, env=env)


def _record_uv(tmp_path: Path, env: dict[str, str], uv: str) -> Path:
    """Observe the real uv process boundary without replacing its behavior."""
    binaries = tmp_path / "binaries"
    binaries.mkdir()
    record = tmp_path / "uv-invocation.json"
    wrapper = binaries / "uv"
    wrapper.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        f"pathlib.Path({str(record)!r}).write_text(json.dumps({{"
        "'args': sys.argv[1:], 'environment': {k: v for k, v in os.environ.items() "
        "if k.startswith('UV_') or k == 'XDG_CACHE_HOME'}}))\n"
        f"os.execv({uv!r}, [{uv!r}, *sys.argv[1:]])\n"
    )
    wrapper.chmod(0o700)
    env["PATH"] = str(binaries) + os.pathsep + env["PATH"]
    return record


def _assert_no_receipt(workspace: Path) -> None:
    assert not (workspace / ".fleet-runtime" / "athena-preparation.json").exists()


def test_seed_creates_fresh_importable_environment_without_index(tmp_path, offline_project):
    workspace, seed, binding, env = _inputs(tmp_path, offline_project)
    original_seed = _cache_sha256(seed)
    result = _prepare(workspace, seed, binding, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _cache_sha256(seed) == original_seed
    runtime_cache = Path(env["XDG_CACHE_HOME"]) / "athena-uv"
    assert runtime_cache.is_dir()
    for path in runtime_cache.rglob("*"):
        assert not path.is_symlink()
        if path.is_file():
            relative = path.relative_to(runtime_cache)
            if (seed / relative).is_file():
                assert not path.samefile(seed / relative)
    imported = _run(
        [str(workspace / ".venv" / "bin" / "python"), "-I", "-c", "import fleet_offline_fixture; print(fleet_offline_fixture.VALUE)"],
        cwd=workspace, env=env,
    )
    assert imported.returncode == 0, imported.stderr
    assert imported.stdout.strip() == "installed-from-seed"
    receipt = json.loads((workspace / ".fleet-runtime" / "athena-preparation.json").read_text())
    assert receipt["snapshot_sha256"] == SNAPSHOT_SHA256
    assert receipt["image_digest"] == IMAGE_DIGEST
    assert receipt["cache_sha256"] == original_seed
    assert receipt["upstream_revision"] == UPSTREAM_REVISION
    assert receipt["dependency_files"] == json.loads(binding.read_text())["dependency_files"]
    assert Path(receipt["environment"]) == workspace / ".venv"
    assert Path(receipt["uv_cache_dir"]) == runtime_cache


@pytest.mark.parametrize("changed_file", DEPENDENCY_FILES)
def test_changed_dependency_input_is_rejected_before_sync(tmp_path, offline_project, changed_file):
    workspace, seed, binding, env = _inputs(tmp_path, offline_project)
    record = _record_uv(tmp_path, env, offline_project[2])
    with (workspace / changed_file).open("a") as changed:
        changed.write("\n# Changed after the seed binding was created.\n")
    result = _prepare(workspace, seed, binding, env)
    assert result.returncode != 0
    assert result.stderr
    assert not record.exists(), "Changed dependency input must be rejected before uv runs."
    assert not (workspace / ".venv").exists()
    _assert_no_receipt(workspace)


def test_changed_seed_is_rejected_before_sync(tmp_path, offline_project):
    workspace, seed, binding, env = _inputs(tmp_path, offline_project)
    record = _record_uv(tmp_path, env, offline_project[2])
    (seed / "unbound-file").write_text("This file was not part of the seed binding.\n")
    result = _prepare(workspace, seed, binding, env)
    assert result.returncode != 0
    assert not record.exists(), "Changed cache input must be rejected before uv runs."
    assert not (workspace / ".venv").exists()
    _assert_no_receipt(workspace)


@pytest.mark.parametrize("ambient_bypass", [False, True], ids=["empty-seed", "ambient-cache-and-bypass"])
def test_missing_offline_dependency_cannot_produce_receipt(tmp_path, offline_project, ambient_bypass):
    workspace, seed, binding, env = _inputs(tmp_path, offline_project)
    shutil.rmtree(seed)
    seed.mkdir()
    _write_binding(workspace, seed, binding)
    record = _record_uv(tmp_path, env, offline_project[2])
    ambient = tmp_path / "ambient-environment"
    ambient.mkdir()
    (ambient / "sentinel").write_text("unchanged")
    if ambient_bypass:
        env.update({
            "UV_NO_SYNC": "1", "UV_FROZEN": "1", "UV_OFFLINE": "0",
            "UV_CACHE_DIR": str(offline_project[1]),
            "UV_PROJECT_ENVIRONMENT": str(ambient),
        })
    original_seed = _cache_sha256(seed)
    result = _prepare(workspace, seed, binding, env)
    assert result.returncode != 0
    assert "fleet-offline-fixture" in result.stderr
    invocation = json.loads(record.read_text())
    assert "--locked" in invocation["args"]
    assert "--offline" in invocation["args"]
    assert invocation["environment"].get("UV_NO_SYNC") is None
    assert invocation["environment"].get("UV_FROZEN") is None
    assert Path(invocation["environment"]["UV_CACHE_DIR"]) == Path(env["XDG_CACHE_HOME"]) / "athena-uv"
    assert Path(invocation["environment"]["UV_PROJECT_ENVIRONMENT"]) == workspace / ".venv"
    assert _cache_sha256(seed) == original_seed
    assert sorted(path.name for path in ambient.iterdir()) == ["sentinel"]
    assert (ambient / "sentinel").read_text() == "unchanged"
    _assert_no_receipt(workspace)


def test_ambient_resolution_settings_cannot_redirect_successful_sync(tmp_path, offline_project):
    workspace, seed, binding, env = _inputs(tmp_path, offline_project)
    record = _record_uv(tmp_path, env, offline_project[2])
    poisoned_settings = {
        "UV_CONFIG_FILE": str(tmp_path / "does-not-exist.toml"),
        "UV_PYTHON": str(tmp_path / "does-not-exist-python"),
        "UV_PROJECT": str(tmp_path / "does-not-exist-project"),
        "UV_INDEX_URL": "http://127.0.0.1:1/wrong-index",
        "UV_DEFAULT_INDEX": "http://127.0.0.1:1/wrong-index",
        "UV_EXTRA_INDEX_URL": "http://127.0.0.1:1/wrong-index",
        "UV_FIND_LINKS": str(tmp_path / "does-not-exist-wheels"),
        "UV_NO_SYNC": "1", "UV_FROZEN": "1", "UV_OFFLINE": "0",
        "UV_PROJECT_ENVIRONMENT": str(tmp_path / "wrong-environment"),
        "UV_CACHE_DIR": str(tmp_path / "wrong-cache"),
        "UV_PYTHON_DOWNLOADS": "automatic",
    }
    env.update(poisoned_settings)
    result = _prepare(workspace, seed, binding, env)
    assert result.returncode == 0, result.stdout + result.stderr
    invocation = json.loads(record.read_text())
    for name, poisoned_value in poisoned_settings.items():
        assert invocation["environment"].get(name) != poisoned_value, name
    assert Path(invocation["environment"]["UV_PYTHON"]).resolve() == Path(sys.executable).resolve()
    assert invocation["environment"]["UV_PYTHON_DOWNLOADS"] == "never"
    assert "--locked" in invocation["args"]
    assert "--offline" in invocation["args"]
    imported = _run(
        [str(workspace / ".venv" / "bin" / "python"), "-I", "-c", "import fleet_offline_fixture; print(fleet_offline_fixture.VALUE)"],
        cwd=workspace, env=_environment(tmp_path / "import-home", offline_project[2]),
    )
    assert imported.returncode == 0, imported.stderr
    assert imported.stdout.strip() == "installed-from-seed"
    assert not (tmp_path / "wrong-environment").exists()
    assert not (tmp_path / "wrong-cache").exists()


def test_read_only_seed_internal_links_become_private_writable_files(tmp_path, offline_project):
    workspace, seed, binding, env = _inputs(tmp_path, offline_project)
    content = seed / "permission-fixture"
    content.mkdir()
    executable = content / "tool"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o500)
    (seed / "logical-link").symlink_to("permission-fixture", target_is_directory=True)
    _write_binding(workspace, seed, binding)
    original_seed = _cache_sha256(seed)
    paths = list(seed.rglob("*"))
    for path in paths:
        if not path.is_symlink():
            path.chmod(0o500 if path.is_dir() or path == executable else 0o400)
    seed.chmod(0o500)
    try:
        result = _prepare(workspace, seed, binding, env)
        assert result.returncode == 0, result.stdout + result.stderr
        copied = Path(env["XDG_CACHE_HOME"]) / "athena-uv" / "logical-link" / "tool"
        assert not copied.parent.is_symlink()
        assert not copied.is_symlink()
        assert not copied.samefile(executable)
        assert copied.stat().st_mode & 0o200
        assert copied.stat().st_mode & 0o100
        copied.write_text("changed only in the workspace\n")
        assert _cache_sha256(seed) == original_seed
        assert executable.read_text() == "#!/bin/sh\nexit 0\n"
    finally:
        seed.chmod(0o700)
        for path in paths:
            if not path.is_symlink():
                path.chmod(0o700 if path.is_dir() else 0o600)


INPUT_PINS = {
    "codex-arm64.tgz": "CODEX_ARM64_SHA256",
    "just-arm64.tar.gz": "JUST_ARM64_SHA256",
    "uv-arm64.tar.gz": "UV_ARM64_SHA256",
    "uv.lock": "ATHENA_LOCK_SHA256",
    "pyproject.toml": "ATHENA_PROJECT_SHA256",
    ".python-version": "ATHENA_PYTHON_SHA256",
}
CONTEXT_SOURCES = ("Dockerfile", "Dockerfile.dockerignore", "prepare_workspace.py", "workspace.just")


@pytest.fixture
def local_input_context(tmp_path):
    repository = tmp_path / "repository"
    scripts = repository / "scripts"
    scripts.mkdir(parents=True)
    script = scripts / "build-athena-tools.sh"
    shutil.copyfile(ROOT / "scripts" / "build-athena-tools.sh", script)
    recipe = repository / "vessels" / "athena-tools"
    recipe.mkdir(parents=True)
    context = tmp_path / "context with spaces"
    inputs = context / "inputs"
    inputs.mkdir(parents=True)
    pins = {
        "CODEX_VERSION": "1.0.0", "JUST_VERSION": "1.0.0", "UV_VERSION": "1.0.0",
        "ATHENA_REVISION": UPSTREAM_REVISION,
    }
    for name, pin in INPUT_PINS.items():
        path = inputs / name
        path.write_bytes(f"small local input for {name}\n".encode())
        pins[pin] = _sha256(path)
    (recipe / "Dockerfile").write_text("\n".join(f"ARG {name}={value}" for name, value in pins.items()) + "\n")
    for name in CONTEXT_SOURCES[1:]:
        (recipe / name).write_text(f"image source fixture: {name}\n")
    binaries = tmp_path / "external-boundaries"
    binaries.mkdir()
    calls = tmp_path / "unexpected-external-calls.txt"
    for name in ("curl", "podman", "docker", "timeout"):
        command = binaries / name
        command.write_text(
            f"#!{sys.executable}\n"
            "from pathlib import Path\n"
            f"with Path({str(calls)!r}).open('a') as output:\n"
            f"    output.write({name!r} + '\\n')\n"
            "raise SystemExit(91)\n"
        )
        command.chmod(0o700)
    env = {
        "PATH": os.pathsep.join((str(binaries), "/usr/bin", "/bin")),
        "HOME": str(tmp_path), "LANG": "C", "CONTAINER_CMD": str(binaries / "podman"),
    }
    return script, recipe, context, calls, env


@pytest.mark.parametrize("changed_input", INPUT_PINS)
def test_wrong_cached_input_prevents_network_and_build(local_input_context, changed_input):
    script, recipe, context, calls, env = local_input_context
    changed = context / "inputs" / changed_input
    changed.write_text("cached bytes do not match the pinned digest\n")
    before = {path.name: _sha256(path) for path in (context / "inputs").iterdir()}
    result = _run(["/bin/bash", str(script), "build", str(context)], cwd=recipe, env=env)
    assert result.returncode != 0
    assert not calls.exists(), "Cached digest mismatch must stop before download or build."
    assert not (context / "Dockerfile").exists()
    assert {path.name: _sha256(path) for path in (context / "inputs").iterdir()} == before


def test_cached_inputs_stage_complete_context_without_network_or_build(local_input_context):
    script, recipe, context, calls, env = local_input_context
    before = {path.name: _sha256(path) for path in (context / "inputs").iterdir()}
    result = _run(["/bin/bash", str(script), "inputs", str(context)], cwd=recipe, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not calls.exists()
    assert {path.name: _sha256(path) for path in (context / "inputs").iterdir()} == before
    for name in CONTEXT_SOURCES:
        assert (context / name).read_bytes() == (recipe / name).read_bytes()
    assert {path.name for path in context.iterdir()} == {"inputs", *CONTEXT_SOURCES}


def _dockerfile_args(path: Path) -> dict[str, str]:
    return dict(re.findall(r"^ARG ([A-Z0-9_]+)=(\S+)$", path.read_text(), flags=re.MULTILINE))


def test_image_pins_match_version_manifest():
    manifest = yaml.safe_load((ROOT / "versions.yml").read_text())["athena_tools"]
    dockerfile = ROOT / "vessels" / "athena-tools" / "Dockerfile"
    args = _dockerfile_args(dockerfile)
    mapping = {
        "GIT_VERSION": "git", "DEBIAN_SNAPSHOT": "debian_snapshot",
        "CODEX_VERSION": "codex", "CODEX_ARM64_SHA256": "codex_arm64_sha256",
        "JUST_VERSION": "just", "JUST_ARM64_SHA256": "just_arm64_sha256",
        "UV_VERSION": "uv", "UV_ARM64_SHA256": "uv_arm64_sha256",
        "ATHENA_REVISION": "athena_revision", "ATHENA_LOCK_SHA256": "lock_sha256",
        "ATHENA_PROJECT_SHA256": "project_sha256", "ATHENA_PYTHON_SHA256": "python_sha256",
    }
    assert {name: args[name] for name in mapping} == {
        name: manifest[key] for name, key in mapping.items()
    }
    bases = re.findall(r"^FROM (\S+)", dockerfile.read_text(), flags=re.MULTILINE)
    assert bases[0] == manifest["python_image"]
    assert manifest["platform"] == "linux/arm64"


def test_ci_uv_pins_match_version_manifest():
    manifest = yaml.safe_load((ROOT / "versions.yml").read_text())["athena_tools"]
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())
    expected = {"UV_VERSION": manifest["uv"], "UV_AMD64_SHA256": manifest["uv_amd64_sha256"]}
    lint_env = workflow["jobs"]["lint"]["env"]
    assert {name: lint_env[name] for name in expected} == expected
    ci_args = _dockerfile_args(ROOT / "ci" / "Containerfile")
    assert {name: ci_args[name] for name in expected} == expected
