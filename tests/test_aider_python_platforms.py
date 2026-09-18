"""Check Aider's native Python selection using captured registry input fixtures.

These offline metadata checks do not build an image or prove runtime success.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

import pytest

from hephaestus.digest import is_valid_digest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/aider-python-registry.json").read_text())
INDEX = "sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea"
OLD_LEAF = "sha256:876416ecde9aca2bcc90e1fb0c7a9500bbf749f5788b70f82d4c5a5c2357f8b4"


def source_digest(dockerfile: str) -> str:
    sources = re.findall(
        r"^FROM\s+(.+?)\s+AS\s+python312-source\s*$", dockerfile, re.MULTILINE | re.IGNORECASE
    )
    assert len(sources) == 1, "Aider must have one Python source stage"
    reference = re.fullmatch(r"python:[\w.-]+@(sha256:[0-9a-f]{64})", sources[0])
    assert reference, "Python source must use an immutable pin without a forced platform"
    return reference.group(1)


def document(digest: str, documents: dict = FIXTURE["documents"]) -> dict:
    assert is_valid_digest(digest), "invalid registry digest"
    assert digest in documents, "capture primary registry documents for this pin"
    # The JSON string preserves the exact HTTP body, without file newline changes.
    body = documents[digest]["body"].encode("utf-8")
    assert "sha256:" + hashlib.sha256(body).hexdigest() == digest, "registry body digest mismatch"
    return json.loads(body)


def native_python(index: dict, architecture: str) -> dict:
    assert index.get("mediaType") == "application/vnd.oci.image.index.v1+json", (
        "Python source must be a platform-selectable index, not a single-platform image"
    )
    matches = [
        item for item in index["manifests"]
        if item.get("platform", {}).get("os") == "linux"
        and item["platform"].get("architecture") == architecture
    ]
    assert len(matches) == 1, f"expected one native linux/{architecture} image"
    manifest = document(matches[0]["digest"])
    config = document(manifest["config"]["digest"])
    assert (config["os"], config["architecture"]) == ("linux", architecture)
    assert "PYTHON_VERSION=3.12.14" in config["config"]["Env"]
    return config


@pytest.mark.parametrize("architecture", ["amd64", "arm64"])
def test_aider_source_selects_native_python(architecture: str) -> None:
    digest = source_digest((ROOT / "vessels/aider/Dockerfile").read_text())
    native_python(document(digest), architecture)


@pytest.mark.parametrize("architecture", ["amd64", "arm64"])
def test_captured_index_has_matching_native_python(architecture: str) -> None:
    native_python(document(INDEX), architecture)


@pytest.mark.parametrize("reference", [
    "python:3.12-slim",
    "--platform=linux/amd64 python:3.12-slim@" + INDEX,
    "foreign.example/python:3.12-slim@" + INDEX,
])
def test_source_rejects_mutable_foreign_or_forced_platform(reference: str) -> None:
    with pytest.raises(AssertionError, match="immutable pin without a forced platform"):
        source_digest(f"FROM {reference} AS python312-source\n")


def test_original_single_platform_pin_is_rejected() -> None:
    with pytest.raises(AssertionError, match="platform-selectable index"):
        native_python(document(OLD_LEAF), "arm64")


def test_corrupted_primary_document_is_rejected() -> None:
    documents = copy.deepcopy(FIXTURE["documents"])
    documents[INDEX]["body"] += " "
    with pytest.raises(AssertionError, match="registry body digest mismatch"):
        document(INDEX, documents)


@pytest.mark.parametrize("copies", [0, 2], ids=["missing", "ambiguous"])
def test_native_platform_requires_one_descriptor(copies: int) -> None:
    index = document(INDEX)
    arm = next(item for item in index["manifests"] if item["platform"]["architecture"] == "arm64")
    index["manifests"] = [
        item for item in index["manifests"] if item["platform"]["architecture"] != "arm64"
    ] + [arm] * copies
    with pytest.raises(AssertionError, match="expected one native linux/arm64"):
        native_python(index, "arm64")
