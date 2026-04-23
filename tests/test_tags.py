"""Tests for hephaestus.tags — date-tag collision-guard logic."""

from __future__ import annotations

from datetime import date

import pytest

from hephaestus.tags import (
    build_date_tag,
    image_tags,
    is_valid_date_tag,
    parse_tags_from_env,
    short_sha,
)

REGISTRY = "ghcr.io/homericintelligence"
FULL_SHA = "abc1234567890abcdef1234567890abcdef12345"
SHORT = "abc1234"
BUILD_DATE = date(2026, 4, 23)


# ---------------------------------------------------------------------------
# short_sha
# ---------------------------------------------------------------------------


class TestShortSha:
    def test_returns_first_seven_chars(self) -> None:
        assert short_sha(FULL_SHA) == SHORT

    def test_already_short(self) -> None:
        assert short_sha("deadbee") == "deadbee"

    def test_lowercases_input(self) -> None:
        assert short_sha("ABC1234FFFFFF") == "abc1234"

    def test_rejects_non_hex(self) -> None:
        with pytest.raises(ValueError, match="Not a valid git SHA"):
            short_sha("not-a-sha!")

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError):
            short_sha("")

    @pytest.mark.parametrize(
        "sha,expected",
        [
            ("0000000000000000000000000000000000000000", "0000000"),
            ("ffffffffffffffffffffffffffffffffffffffff", "fffffff"),
            ("1234567abcdef12", "1234567"),
        ],
    )
    def test_various_shas(self, sha: str, expected: str) -> None:
        assert short_sha(sha) == expected


# ---------------------------------------------------------------------------
# build_date_tag
# ---------------------------------------------------------------------------


class TestBuildDateTag:
    def test_format(self) -> None:
        tag = build_date_tag(BUILD_DATE, FULL_SHA)
        assert tag == f"2026-04-23-{SHORT}"

    def test_is_valid_date_tag(self) -> None:
        tag = build_date_tag(BUILD_DATE, FULL_SHA)
        assert is_valid_date_tag(tag)

    def test_different_dates_different_tags(self) -> None:
        t1 = build_date_tag(date(2026, 4, 10), FULL_SHA)
        t2 = build_date_tag(date(2026, 4, 11), FULL_SHA)
        assert t1 != t2

    def test_same_date_different_sha_different_tags(self) -> None:
        sha2 = "deadbeef0000000"
        t1 = build_date_tag(BUILD_DATE, FULL_SHA)
        t2 = build_date_tag(BUILD_DATE, sha2)
        assert t1 != t2


# ---------------------------------------------------------------------------
# is_valid_date_tag
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tag,expected",
    [
        ("2026-04-23-abc1234", True),
        ("2026-04-23-0000000", True),
        ("2026-04-23-fffffff", True),
        # wrong lengths / formats
        ("2026-04-23-abc123", False),   # SHA too short (6 chars)
        ("2026-04-23-abc12345", False), # SHA too long (8 chars)
        ("26-04-23-abc1234", False),    # year too short
        ("2026-4-23-abc1234", False),   # month without leading zero
        ("2026-04-23abc1234", False),   # missing dash before SHA
        ("latest", False),
        ("git-abc1234", False),
        ("", False),
    ],
)
def test_is_valid_date_tag(tag: str, expected: bool) -> None:
    assert is_valid_date_tag(tag) == expected


# ---------------------------------------------------------------------------
# image_tags
# ---------------------------------------------------------------------------


class TestImageTags:
    def test_returns_three_tags(self) -> None:
        tags = image_tags(REGISTRY, "achaean-claude", FULL_SHA, BUILD_DATE)
        assert len(tags) == 3

    def test_latest_tag(self) -> None:
        tags = image_tags(REGISTRY, "achaean-claude", FULL_SHA, BUILD_DATE)
        assert f"{REGISTRY}/achaean-claude:latest" in tags

    def test_git_tag(self) -> None:
        tags = image_tags(REGISTRY, "achaean-claude", FULL_SHA, BUILD_DATE)
        assert f"{REGISTRY}/achaean-claude:git-{SHORT}" in tags

    def test_date_tag(self) -> None:
        tags = image_tags(REGISTRY, "achaean-claude", FULL_SHA, BUILD_DATE)
        assert f"{REGISTRY}/achaean-claude:2026-04-23-{SHORT}" in tags

    def test_date_tag_is_valid_format(self) -> None:
        tags = image_tags(REGISTRY, "achaean-claude", FULL_SHA, BUILD_DATE)
        date_tags = [t for t in tags if is_valid_date_tag(t.split(":")[-1])]
        assert len(date_tags) == 1

    def test_trailing_slash_stripped_from_registry(self) -> None:
        tags = image_tags(REGISTRY + "/", "achaean-worker", FULL_SHA, BUILD_DATE)
        assert all("//" not in t for t in tags)

    def test_same_day_two_shas_distinct_date_tags(self) -> None:
        sha2 = "deadbeef1234567"
        tags1 = image_tags(REGISTRY, "achaean-claude", FULL_SHA, BUILD_DATE)
        tags2 = image_tags(REGISTRY, "achaean-claude", sha2, BUILD_DATE)
        date_tag1 = next(t for t in tags1 if is_valid_date_tag(t.split(":")[-1]))
        date_tag2 = next(t for t in tags2 if is_valid_date_tag(t.split(":")[-1]))
        assert date_tag1 != date_tag2, "Same-day pushes must produce distinct date tags"

    def test_defaults_build_date_to_today(self) -> None:
        tags = image_tags(REGISTRY, "achaean-claude", FULL_SHA)
        today = date.today().isoformat()
        assert any(today in t for t in tags)

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
    def test_all_vessel_names(self, image_name: str) -> None:
        tags = image_tags(REGISTRY, image_name, FULL_SHA, BUILD_DATE)
        assert len(tags) == 3
        assert any(image_name in t for t in tags)


# ---------------------------------------------------------------------------
# parse_tags_from_env
# ---------------------------------------------------------------------------


class TestParseTagsFromEnv:
    def test_returns_mapping_for_each_image(self) -> None:
        result = parse_tags_from_env(
            REGISTRY,
            ["achaean-claude", "achaean-worker"],
            FULL_SHA,
            "2026-04-23",
        )
        assert set(result) == {"achaean-claude", "achaean-worker"}

    def test_each_image_has_three_tags(self) -> None:
        result = parse_tags_from_env(
            REGISTRY,
            ["achaean-claude"],
            FULL_SHA,
            "2026-04-23",
        )
        assert len(result["achaean-claude"]) == 3

    def test_rejects_invalid_date_string(self) -> None:
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            parse_tags_from_env(REGISTRY, ["achaean-claude"], FULL_SHA, "not-a-date")

    def test_rejects_wrong_date_format(self) -> None:
        with pytest.raises(ValueError):
            parse_tags_from_env(REGISTRY, ["achaean-claude"], FULL_SHA, "23-04-2026")

    def test_empty_image_list(self) -> None:
        result = parse_tags_from_env(REGISTRY, [], FULL_SHA, "2026-04-23")
        assert result == {}
