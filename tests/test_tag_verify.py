"""Tests for hephaestus.tag_verify — post-push GHCR tag verification helpers."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from hephaestus.tag_verify import (
    ImageTags,
    assert_all_tags_present,
    build_image_tags,
    manifest_inspect,
    verify_tags,
    REGISTRY,
    SENTINEL_IMAGE,
)


IMAGE = "ghcr.io/homericintelligence/achaean-claude"
SHA = "abc1234"
DATE = "20260423"


# ---------------------------------------------------------------------------
# build_image_tags
# ---------------------------------------------------------------------------


class TestBuildImageTags:
    def test_returns_image_tags_instance(self) -> None:
        tags = build_image_tags(IMAGE, SHA, DATE)
        assert isinstance(tags, ImageTags)

    def test_latest_tag(self) -> None:
        tags = build_image_tags(IMAGE, SHA, DATE)
        assert tags.latest == f"{IMAGE}:latest"

    def test_sha_tag(self) -> None:
        tags = build_image_tags(IMAGE, SHA, DATE)
        assert tags.sha == f"{IMAGE}:git-{SHA}"

    def test_date_tag(self) -> None:
        tags = build_image_tags(IMAGE, SHA, DATE)
        assert tags.date == f"{IMAGE}:{DATE}"

    def test_all_tags_order(self) -> None:
        tags = build_image_tags(IMAGE, SHA, DATE)
        assert tags.all_tags() == [tags.latest, tags.sha, tags.date]

    @pytest.mark.parametrize("bad_sha", ["abc123", "ABCDEFG", "abc123g", "abc12345", ""])
    def test_invalid_sha_raises(self, bad_sha: str) -> None:
        with pytest.raises(ValueError, match="sha must be 7 lowercase hex chars"):
            build_image_tags(IMAGE, bad_sha, DATE)

    @pytest.mark.parametrize("bad_date", ["2026-04-23", "202604", "20260423x", ""])
    def test_invalid_date_raises(self, bad_date: str) -> None:
        with pytest.raises(ValueError, match="date must be YYYYMMDD format"):
            build_image_tags(IMAGE, SHA, bad_date)

    @pytest.mark.parametrize(
        "sha,date",
        [
            ("0000000", "20260101"),
            ("fffffff", "99991231"),
            ("1234567", "20260423"),
        ],
    )
    def test_valid_sha_and_date_combinations(self, sha: str, date: str) -> None:
        tags = build_image_tags(IMAGE, sha, date)
        assert tags.sha == f"{IMAGE}:git-{sha}"
        assert tags.date == f"{IMAGE}:{date}"


# ---------------------------------------------------------------------------
# module-level constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_registry_value(self) -> None:
        assert REGISTRY == "ghcr.io/homericintelligence"

    def test_sentinel_image_value(self) -> None:
        assert SENTINEL_IMAGE == "ghcr.io/homericintelligence/achaean-claude"

    def test_sentinel_image_uses_registry(self) -> None:
        assert SENTINEL_IMAGE.startswith(REGISTRY)


# ---------------------------------------------------------------------------
# manifest_inspect
# ---------------------------------------------------------------------------


class TestManifestInspect:
    def test_returns_true_on_zero_exit(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = manifest_inspect("ghcr.io/example/image:latest")
        assert result is True
        mock_run.assert_called_once_with(
            ["docker", "manifest", "inspect", "ghcr.io/example/image:latest"],
            capture_output=True,
        )

    def test_returns_false_on_nonzero_exit(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            result = manifest_inspect("ghcr.io/example/image:missing")
        assert result is False

    @pytest.mark.parametrize("returncode", [2, 127, 255])
    def test_returns_false_on_any_nonzero_exit(self, returncode: int) -> None:
        mock_result = MagicMock()
        mock_result.returncode = returncode
        with patch("subprocess.run", return_value=mock_result):
            result = manifest_inspect("ghcr.io/example/image:tag")
        assert result is False


# ---------------------------------------------------------------------------
# verify_tags
# ---------------------------------------------------------------------------


class TestVerifyTags:
    def _make_tags(self) -> ImageTags:
        return build_image_tags(IMAGE, SHA, DATE)

    def test_all_present(self) -> None:
        tags = self._make_tags()
        with patch("hephaestus.tag_verify.manifest_inspect", return_value=True):
            results = verify_tags(tags)
        assert results == {tags.latest: True, tags.sha: True, tags.date: True}

    def test_all_missing(self) -> None:
        tags = self._make_tags()
        with patch("hephaestus.tag_verify.manifest_inspect", return_value=False):
            results = verify_tags(tags)
        assert all(v is False for v in results.values())

    def test_partial_missing(self) -> None:
        tags = self._make_tags()
        # Only the sha tag is missing
        def side_effect(tag: str) -> bool:
            return tag != tags.sha

        with patch("hephaestus.tag_verify.manifest_inspect", side_effect=side_effect):
            results = verify_tags(tags)

        assert results[tags.latest] is True
        assert results[tags.sha] is False
        assert results[tags.date] is True

    def test_returns_all_three_keys(self) -> None:
        tags = self._make_tags()
        with patch("hephaestus.tag_verify.manifest_inspect", return_value=True):
            results = verify_tags(tags)
        assert set(results.keys()) == {tags.latest, tags.sha, tags.date}


# ---------------------------------------------------------------------------
# assert_all_tags_present
# ---------------------------------------------------------------------------


class TestAssertAllTagsPresent:
    def _make_tags(self) -> ImageTags:
        return build_image_tags(IMAGE, SHA, DATE)

    def test_passes_when_all_present(self) -> None:
        tags = self._make_tags()
        with patch("hephaestus.tag_verify.manifest_inspect", return_value=True):
            assert_all_tags_present(tags)  # must not raise

    def test_raises_when_latest_missing(self) -> None:
        tags = self._make_tags()

        def side_effect(tag: str) -> bool:
            return tag != tags.latest

        with patch("hephaestus.tag_verify.manifest_inspect", side_effect=side_effect):
            with pytest.raises(AssertionError) as exc_info:
                assert_all_tags_present(tags)
        assert tags.latest in str(exc_info.value)

    def test_raises_when_sha_missing(self) -> None:
        tags = self._make_tags()

        def side_effect(tag: str) -> bool:
            return tag != tags.sha

        with patch("hephaestus.tag_verify.manifest_inspect", side_effect=side_effect):
            with pytest.raises(AssertionError) as exc_info:
                assert_all_tags_present(tags)
        assert tags.sha in str(exc_info.value)

    def test_raises_when_date_missing(self) -> None:
        tags = self._make_tags()

        def side_effect(tag: str) -> bool:
            return tag != tags.date

        with patch("hephaestus.tag_verify.manifest_inspect", side_effect=side_effect):
            with pytest.raises(AssertionError) as exc_info:
                assert_all_tags_present(tags)
        assert tags.date in str(exc_info.value)

    def test_raises_when_all_missing(self) -> None:
        tags = self._make_tags()
        with patch("hephaestus.tag_verify.manifest_inspect", return_value=False):
            with pytest.raises(AssertionError) as exc_info:
                assert_all_tags_present(tags)
        error_msg = str(exc_info.value)
        assert tags.latest in error_msg
        assert tags.sha in error_msg
        assert tags.date in error_msg

    def test_error_message_lists_missing_tags(self) -> None:
        tags = self._make_tags()
        with patch("hephaestus.tag_verify.manifest_inspect", return_value=False):
            with pytest.raises(AssertionError, match="missing from the registry"):
                assert_all_tags_present(tags)
