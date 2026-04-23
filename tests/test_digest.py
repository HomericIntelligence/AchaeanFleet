"""Tests for hephaestus.digest — digest capture and validation utilities."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from hephaestus.digest import (
    format_summary_table,
    inspect_digest,
    is_valid_digest,
)


# ---------------------------------------------------------------------------
# is_valid_digest
# ---------------------------------------------------------------------------

VALID_DIGEST = "sha256:" + "a" * 64


@pytest.mark.parametrize(
    "digest,expected",
    [
        (VALID_DIGEST, True),
        ("sha256:" + "f" * 64, True),
        ("sha256:" + "0123456789abcdef" * 4, True),
        # wrong algorithm prefix
        ("md5:abc123", False),
        # too short
        ("sha256:" + "a" * 63, False),
        # too long
        ("sha256:" + "a" * 65, False),
        # uppercase hex (Docker IDs use lowercase)
        ("sha256:" + "A" * 64, False),
        # empty string
        ("", False),
        # no prefix
        ("a" * 64, False),
    ],
)
def test_is_valid_digest(digest: str, expected: bool) -> None:
    assert is_valid_digest(digest) == expected


# ---------------------------------------------------------------------------
# inspect_digest
# ---------------------------------------------------------------------------

def _mock_run(stdout: str, returncode: int = 0) -> MagicMock:
    mock = MagicMock()
    mock.stdout = stdout
    mock.returncode = returncode
    return mock


@patch("hephaestus.digest.subprocess.run")
def test_inspect_digest_returns_stripped_digest(mock_run: MagicMock) -> None:
    mock_run.return_value = _mock_run(stdout=VALID_DIGEST + "\n")
    result = inspect_digest("achaean-claude:latest")
    assert result == VALID_DIGEST
    mock_run.assert_called_once_with(
        ["docker", "inspect", "--format", "{{.Id}}", "achaean-claude:latest"],
        capture_output=True,
        text=True,
        check=True,
    )


@patch("hephaestus.digest.subprocess.run")
def test_inspect_digest_raises_on_empty_output(mock_run: MagicMock) -> None:
    mock_run.return_value = _mock_run(stdout="")
    with pytest.raises(ValueError, match="empty digest"):
        inspect_digest("achaean-claude:latest")


@patch("hephaestus.digest.subprocess.run")
def test_inspect_digest_raises_on_whitespace_only_output(mock_run: MagicMock) -> None:
    mock_run.return_value = _mock_run(stdout="   \n")
    with pytest.raises(ValueError, match="empty digest"):
        inspect_digest("achaean-claude:latest")


@patch("hephaestus.digest.subprocess.run")
def test_inspect_digest_propagates_called_process_error(mock_run: MagicMock) -> None:
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=["docker", "inspect"]
    )
    with pytest.raises(subprocess.CalledProcessError):
        inspect_digest("nonexistent-image:latest")


# ---------------------------------------------------------------------------
# format_summary_table
# ---------------------------------------------------------------------------

def test_format_summary_table_contains_required_fields() -> None:
    table = format_summary_table(
        image_name="achaean-claude",
        digest=VALID_DIGEST,
        commit_sha="abc123",
    )
    assert "achaean-claude:latest" in table
    assert VALID_DIGEST in table
    assert "abc123" in table


def test_format_summary_table_is_valid_markdown() -> None:
    table = format_summary_table(
        image_name="achaean-worker",
        digest=VALID_DIGEST,
        commit_sha="deadbeef",
    )
    assert table.startswith("## Image Digest:")
    assert "| Field | Value |" in table
    assert "| --- | --- |" in table


@pytest.mark.parametrize(
    "image_name",
    [
        "achaean-claude",
        "achaean-codex",
        "achaean-aider",
        "achaean-goose",
        "achaean-cline",
        "achaean-opencode",
        "achaean-codebuff",
        "achaean-ampcode",
        "achaean-worker",
    ],
)
def test_format_summary_table_all_vessel_names(image_name: str) -> None:
    table = format_summary_table(
        image_name=image_name,
        digest=VALID_DIGEST,
        commit_sha="cafebabe",
    )
    assert f"{image_name}:latest" in table


def test_format_summary_table_ends_with_newline() -> None:
    table = format_summary_table("achaean-claude", VALID_DIGEST, "abc123")
    assert table.endswith("\n")
