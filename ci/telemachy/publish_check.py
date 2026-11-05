"""Prove the published Telemachy CI image is readable without credentials.

Telemachy's required checks run from a public repository and pull this image
with no package credentials, so a publish is only complete once an anonymous
GHCR client can resolve every consumed tag. GHCR creates container packages as
private, so the check makes the package public when the publishing token is
allowed to, then verifies the anonymous pull path itself.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from typing import Any

API = "https://api.github.com"
REGISTRY = "https://ghcr.io"
MANIFEST_TYPES = (
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
)
MANIFEST_ACCEPT = ", ".join(MANIFEST_TYPES)

Fetch = Callable[[urllib.request.Request], bytes]


class PublicationError(RuntimeError):
    """The published artifact cannot be consumed without credentials."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def default_fetch(request: urllib.request.Request) -> bytes:
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310  # fixed https endpoints
        return response.read()


def _send(request: urllib.request.Request, fetch: Fetch) -> bytes:
    try:
        return fetch(request)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace").strip()
        raise PublicationError(
            f"{request.full_url} returned HTTP {error.code}: {detail}",
            status=error.code,
        ) from error


def _api_request(
    url: str,
    token: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> urllib.request.Request:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = None if payload is None else json.dumps(payload).encode()
    if data is not None:
        headers["Content-Type"] = "application/json"
    return urllib.request.Request(url, data=data, headers=headers, method=method)


def package_visibility(
    *, owner: str, image: str, token: str, fetch: Fetch = default_fetch
) -> str:
    """Return the package visibility GitHub reports for the published image."""
    url = f"{API}/orgs/{owner}/packages/container/{image}"
    visibility = json.loads(_send(_api_request(url, token), fetch)).get("visibility")
    if not isinstance(visibility, str):
        raise PublicationError(f"{url} did not report a package visibility")
    return visibility


def ensure_public(
    *, owner: str, image: str, token: str, fetch: Fetch = default_fetch
) -> str:
    """Make the package public and return the visibility GitHub then reports.

    Returns ``"unknown"`` when the token cannot read organization package
    metadata at all. That is the normal case for an Actions workflow token, so
    it must not fail the publish: the anonymous pull probe that follows is the
    contract that actually matters, and it fails loudly for a private package.
    """
    try:
        visibility = package_visibility(
            owner=owner, image=image, token=token, fetch=fetch
        )
    except PublicationError as error:
        if error.status in (403, 404):
            return "unknown"
        raise
    if visibility == "public":
        return visibility
    url = f"{API}/orgs/{owner}/packages/container/{image}"
    _send(
        _api_request(url, token, method="PATCH", payload={"visibility": "public"}),
        fetch,
    )
    visibility = package_visibility(owner=owner, image=image, token=token, fetch=fetch)
    if visibility != "public":
        raise PublicationError(
            f"Package {image} is still {visibility} after an explicit visibility change"
        )
    return visibility


def anonymous_token(
    *, namespace: str, image: str, fetch: Fetch = default_fetch
) -> str:
    """Return a GHCR pull token issued without any credentials."""
    url = f"{REGISTRY}/token?scope=repository:{namespace}/{image}:pull&service=ghcr.io"
    token = json.loads(_send(urllib.request.Request(url), fetch)).get("token")
    if not isinstance(token, str) or not token:
        raise PublicationError(
            f"GHCR refuses an anonymous pull token for {namespace}/{image}; "
            "Telemachy's public workflows cannot pull a private package. Make the "
            "package public once in the organization package settings, or set a "
            "PACKAGES_ADMIN_TOKEN secret so this job can do it."
        )
    return token


def assert_anonymous_manifest(
    *, namespace: str, image: str, tag: str, fetch: Fetch = default_fetch
) -> None:
    """Assert the anonymous path resolves one published tag."""
    token = anonymous_token(namespace=namespace, image=image, fetch=fetch)
    _send(
        urllib.request.Request(
            f"{REGISTRY}/v2/{namespace}/{image}/manifests/{tag}",
            headers={"Authorization": f"Bearer {token}", "Accept": MANIFEST_ACCEPT},
            method="HEAD",
        ),
        fetch,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True, help="organization owning the package")
    parser.add_argument("--image", required=True, help="container image name")
    parser.add_argument(
        "--tags", nargs="+", required=True, help="published tags Telemachy consumes"
    )
    parser.add_argument(
        "--ensure-public",
        action="store_true",
        help="make the package public before verifying",
    )
    arguments = parser.parse_args(argv)

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("Publication check failed: set GH_TOKEN or GITHUB_TOKEN", file=sys.stderr)
        return 1

    namespace = arguments.owner.lower()
    try:
        if arguments.ensure_public:
            visibility = ensure_public(
                owner=arguments.owner, image=arguments.image, token=token
            )
            if visibility == "unknown":
                print(
                    "Package visibility is unreadable for this token; "
                    "relying on the anonymous pull probe."
                )
            else:
                print(f"Package visibility: {visibility}")
        for tag in arguments.tags:
            assert_anonymous_manifest(
                namespace=namespace, image=arguments.image, tag=tag
            )
            print(f"Anonymous pull OK: {namespace}/{arguments.image}:{tag}")
    except PublicationError as error:
        print(f"Publication check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
