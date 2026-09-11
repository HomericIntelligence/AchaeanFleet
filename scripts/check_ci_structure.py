"""Shared lightweight source gates; these do not build, install, or publish images."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def parse(path: Path) -> list[dict]:
    from dockerfile_parse import DockerfileParser

    with path.open("rb") as stream:
        return DockerfileParser(fileobj=stream).structure


def vessels(root: Path) -> list[Path]:
    paths = sorted(path for path in root.glob("vessels/*/Dockerfile") if path.is_file())
    require(bool(paths), "No vessel Dockerfiles found")
    return paths


def check(root: Path, mode: str) -> None:
    if mode == "build":
        paths = sorted(path for path in root.rglob("Dockerfile*")
                       if path.is_file() and ".git" not in path.relative_to(root).parts
                       and ".pixi" not in path.relative_to(root).parts)
        for path in paths:
            structure = parse(path)
            print(f"Parsed {path.relative_to(root)}: {sum(s['instruction'] == 'FROM' for s in structure)} FROM instructions")
        print(f"Dockerfile syntax checked: {len(paths)} files")
    elif mode == "test":
        tests = root / "tests"
        require(tests.is_dir(), "tests/ is missing")
        require(any(tests.rglob("*.bats")) or any(tests.rglob("test_*.py")), "No test suites found")
        for directory in (tests, root / "scripts"):
            for path in sorted(directory.rglob("*")):
                if path.is_file() and path.suffix in (".sh", ".bash"):
                    subprocess.run(["bash", "-n", str(path)], check=True)
        for path in sorted(tests.rglob("*.bats")):
            require(bool(re.search(r"^\s*@test\b", path.read_text(), re.M)), f"No @test cases: {path}")
        print("Test harness and shell syntax checked")
    elif mode == "package":
        bases = sorted(path for path in root.glob("bases/Dockerfile.*") if path.is_file())
        require(bool(bases), "No base Dockerfiles found")
        for path in vessels(root):
            require(any(s["instruction"] == "FROM" for s in parse(path)), f"No FROM: {path}")
        for path in bases:
            parse(path)
        print("Vessel/base Dockerfile configuration checked; no image built")
    elif mode == "install":
        for path in vessels(root):
            content = path.read_text()
            require(bool(re.search(r"^(ENTRYPOINT|CMD)\b", content, re.M)
                         or re.search(r"^(ARG BASE_IMAGE=|FROM ).*achaean-base", content, re.M | re.I)),
                    f"No declared or inherited entrypoint: {path}")
        require((root / "tests/entrypoint.bats").is_file() or (root / "tests/shell").is_dir(),
                "No entrypoint smoke-test harness")
        print("Entrypoint declarations and harness checked; no image started")
    elif mode == "release":
        path = root / ".github/workflows/release.yml"
        require(path.is_file(), "release.yml is missing")
        content = path.read_text()
        require(bool(re.search(r'^\s*-\s*"?v\*\.\*\.\*"?', content, re.M)), "Release tag gate is missing")
        references = set(re.findall(r"vessels/[a-z0-9-]+/Dockerfile", content))
        require(bool(references), "No literal release vessel references")
        for reference in references:
            require((root / reference).is_file(), f"Missing release vessel: {reference}")
        require("push: true" in content, "Release publish step is missing")
        require("Validate tag matches semver" in content, "Release semver validation is missing")
        print("Release configuration checked; no registry write")
    else:
        raise ValueError("Unsupported source gate")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("build", "test", "package", "install", "release"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        check(args.root, args.mode)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"CI source gate: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
