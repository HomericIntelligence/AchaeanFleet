"""Tests for the Telemachy CI image publication guard."""

from __future__ import annotations

import importlib.util
import io
import json
import urllib.error
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).parents[1] / "ci" / "telemachy" / "publish_check.py"
SPEC = importlib.util.spec_from_file_location("telemachy_publish_check", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
publish_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publish_check)

OWNER = "HomericIntelligence"
NAMESPACE = "homericintelligence"
IMAGE = "achaean-telemachy-ci"


class FakeGhcr:
    """Serve the GitHub package API and the GHCR token endpoint."""

    def __init__(self, visibility: str = "private", anonymous: bool = True) -> None:
        self.visibility = visibility
        self.anonymous = anonymous
        self.requests: list[Any] = []

    def __call__(self, request: Any) -> bytes:
        self.requests.append(request)
        if "/packages/container/" in request.full_url:
            if request.get_method() == "PATCH":
                self.visibility = json.loads(request.data)["visibility"]
                return b"{}"
            return json.dumps({"visibility": self.visibility}).encode()
        if "/token?scope=" in request.full_url:
            if not self.anonymous:
                return b'{"errors":[{"code":"UNAUTHORIZED"}]}'
            return b'{"token":"anonymous-pull-token"}'
        return b""

    def methods(self) -> list[str]:
        return [request.get_method() for request in self.requests]


def test_private_package_is_promoted_before_verification() -> None:
    fake = FakeGhcr(visibility="private")

    assert publish_check.ensure_public(
        owner=OWNER, image=IMAGE, token="publisher", fetch=fake
    ) == "public"
    assert fake.methods().count("PATCH") == 1
    patch = next(r for r in fake.requests if r.get_method() == "PATCH")
    assert json.loads(patch.data) == {"visibility": "public"}


def test_public_package_is_left_untouched() -> None:
    fake = FakeGhcr(visibility="public")

    assert publish_check.ensure_public(
        owner=OWNER, image=IMAGE, token="publisher", fetch=fake
    ) == "public"
    assert "PATCH" not in fake.methods()


class DeniedPackageApi(FakeGhcr):
    """Refuse organization package metadata the way an Actions token is refused."""

    def __call__(self, request: Any) -> bytes:
        if "/packages/container/" in request.full_url:
            self.requests.append(request)
            raise urllib.error.HTTPError(
                request.full_url,
                404,
                "Not Found",
                {},
                io.BytesIO(b'{"message":"Not Found"}'),
            )
        return super().__call__(request)


def test_unreadable_metadata_is_not_fatal_for_the_publisher() -> None:
    fake = DeniedPackageApi(visibility="private")

    assert (
        publish_check.ensure_public(
            owner=OWNER, image=IMAGE, token="workflow", fetch=fake
        )
        == "unknown"
    )
    assert "PATCH" not in fake.methods()


class DeniedVisibilityChange(FakeGhcr):
    """Read the package, but refuse to change its visibility."""

    def __call__(self, request: Any) -> bytes:
        if "/packages/container/" in request.full_url and request.get_method() == "PATCH":
            self.requests.append(request)
            raise urllib.error.HTTPError(
                request.full_url,
                404,
                "Not Found",
                {},
                io.BytesIO(b'{"message":"Not Found"}'),
            )
        return super().__call__(request)


def test_denied_visibility_change_defers_to_the_anonymous_probe() -> None:
    fake = DeniedVisibilityChange(visibility="private")

    assert (
        publish_check.ensure_public(
            owner=OWNER, image=IMAGE, token="workflow", fetch=fake
        )
        == "unknown"
    )
    assert "PATCH" in fake.methods()


def test_anonymous_pull_is_rejected_for_a_private_package() -> None:
    fake = FakeGhcr(anonymous=False)

    with pytest.raises(publish_check.PublicationError, match="anonymous pull token"):
        publish_check.anonymous_token(namespace=NAMESPACE, image=IMAGE, fetch=fake)


def test_manifest_probe_carries_the_anonymous_token_only() -> None:
    fake = FakeGhcr(visibility="public")

    publish_check.assert_anonymous_manifest(
        namespace=NAMESPACE, image=IMAGE, tag="git-abc1234", fetch=fake
    )

    manifest = next(r for r in fake.requests if "/manifests/" in r.full_url)
    assert manifest.get_method() == "HEAD"
    assert manifest.get_header("Authorization") == "Bearer anonymous-pull-token"
    assert manifest.full_url.endswith(f"/v2/{NAMESPACE}/{IMAGE}/manifests/git-abc1234")
