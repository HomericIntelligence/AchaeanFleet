"""Tests for the Telemachy CI image publication guard."""

from __future__ import annotations

import importlib.util
import io
import urllib.error
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "ci" / "telemachy" / "publish_check.py"
SPEC = importlib.util.spec_from_file_location("telemachy_publish_check", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
publish_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publish_check)

OWNER = "HomericIntelligence"
NAMESPACE = "homericintelligence"
IMAGE = "achaean-telemachy-ci"
SECRET = "TELEMACHY_GHCR_TOKEN"


class FakeGhcr:
    """Serve the GHCR token endpoint and manifest probes for one credential."""

    def __init__(self, credential: str = "consumer", accepts: bool = True) -> None:
        self.credential = credential
        self.accepts = accepts
        self.requests: list[Any] = []

    def __call__(self, request: Any) -> bytes:
        self.requests.append(request)
        if "/token?scope=" in request.full_url:
            if not self.accepts or request.get_header("Authorization") != (
                f"Bearer {self.credential}"
            ):
                raise urllib.error.HTTPError(
                    request.full_url,
                    403,
                    "Forbidden",
                    {},
                    io.BytesIO(b'{"errors":[{"code":"DENIED"}]}'),
                )
            return b'{"token":"pull-token"}'
        if "/packages/container/" in request.full_url:
            return b'{"visibility":"private"}'
        return b""


def test_pull_token_requests_only_the_repository_pull_scope() -> None:
    fake = FakeGhcr()

    token = publish_check.pull_token(
        namespace=NAMESPACE, image=IMAGE, credential="consumer", fetch=fake
    )

    assert token == "pull-token"
    request = fake.requests[0]
    assert request.full_url == (
        "https://ghcr.io/token?scope=repository:"
        f"{NAMESPACE}/{IMAGE}:pull&service=ghcr.io"
    )
    assert request.get_header("Authorization") == "Bearer consumer"


def test_manifest_probe_carries_the_minted_token() -> None:
    fake = FakeGhcr()

    publish_check.assert_manifest(
        namespace=NAMESPACE, image=IMAGE, tag="git-abc1234", credential="consumer", fetch=fake
    )

    manifest = next(r for r in fake.requests if "/manifests/" in r.full_url)
    assert manifest.get_method() == "HEAD"
    assert manifest.get_header("Authorization") == "Bearer pull-token"
    assert "application/vnd.oci.image.index.v1+json" in manifest.get_header("Accept")
    assert manifest.full_url.endswith(f"/v2/{NAMESPACE}/{IMAGE}/manifests/git-abc1234")


def test_rejected_credential_names_the_secret_to_create() -> None:
    fake = FakeGhcr(accepts=False)

    with pytest.raises(publish_check.PublicationError) as raised:
        publish_check.assert_manifest(
            namespace=NAMESPACE, image=IMAGE, tag="ci", credential="consumer", fetch=fake
        )

    message = str(raised.value)
    assert SECRET in message
    assert "read:packages" in message


def test_visibility_is_reported_but_never_changed() -> None:
    fake = FakeGhcr()

    visibility = publish_check.package_visibility(
        owner=OWNER, image=IMAGE, token="reader", fetch=fake
    )

    assert visibility == "private"
    assert all(request.get_method() != "PATCH" for request in fake.requests)


def test_missing_credential_fails_before_probing_the_registry(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(publish_check.CREDENTIAL_ENV, raising=False)
    fake = FakeGhcr()
    monkeypatch.setattr(publish_check, "default_fetch", fake)

    status = publish_check.main(["--owner", OWNER, "--image", IMAGE, "--tags", "ci"])

    assert status == 1
    assert fake.requests == []
    assert SECRET in capsys.readouterr().err


def test_every_consumed_tag_is_verified_with_the_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeGhcr()
    monkeypatch.setenv(publish_check.CREDENTIAL_ENV, "consumer")
    monkeypatch.setattr(publish_check, "default_fetch", fake)

    status = publish_check.main(
        ["--owner", OWNER, "--image", IMAGE, "--tags", "ci", "git-abc1234"]
    )

    assert status == 0
    probes = [r.full_url for r in fake.requests if "/manifests/" in r.full_url]
    assert [url.rsplit("/", 1)[1] for url in probes] == ["ci", "git-abc1234"]


def test_publish_workflow_supplies_the_consumer_credential() -> None:
    workflow = (ROOT / ".github" / "workflows" / "telemachy-ci.yml").read_text()

    assert f"secrets.{SECRET}" in workflow
    assert "--ensure-public" not in workflow
    assert "packages: write" in workflow
