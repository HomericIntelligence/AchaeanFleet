"""Prove Telemachy's credential can pull the published Telemachy CI image.

Organization policy forbids public container packages, so
``ghcr.io/homericintelligence/achaean-telemachy-ci`` stays private and
Telemachy's required jobs pull it with a credential CI owns. A publish is
therefore only complete once that same credential resolves every consumed tag.

The check mints a GHCR pull token from the credential exactly as a container
client would, then probes each tag with it. An artifact that only the
publishing repository can read fails here instead of failing Telemachy's
required checks.
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
CREDENTIAL_ENV = "GHCR_PULL_TOKEN"
CREDENTIAL_SECRET = "TELEMACHY_GHCR_TOKEN"

Fetch = Callable[[urllib.request.Request], bytes]


class PublicationError(RuntimeError):
    """The published artifact cannot be consumed with Telemachy's credential."""

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


def credential_from_environment() -> str:
    """Return Telemachy's registry credential without ever echoing it."""
    credential = os.environ.get(CREDENTIAL_ENV, "")
    if not credential:
        raise PublicationError(
            f"set {CREDENTIAL_ENV} to the value of the {CREDENTIAL_SECRET} secret. "
            "The package is private because organization policy forbids public "
            "container packages, so a publish that only the publishing repository "
            "can read is not consumable."
        )
    return credential


def pull_token(
    *, namespace: str, image: str, credential: str | None = None, fetch: Fetch | None = None
) -> str:
    """Return a GHCR pull token minted from Telemachy's credential."""
    fetch = fetch or default_fetch
    credential = credential or credential_from_environment()
    url = f"{REGISTRY}/token?scope=repository:{namespace}/{image}:pull&service=ghcr.io"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {credential}"})
    try:
        token = json.loads(_send(request, fetch)).get("token")
    except PublicationError as error:
        raise PublicationError(
            f"GHCR refuses a pull token for {namespace}/{image} with the "
            f"{CREDENTIAL_SECRET} credential ({error}). Give Telemachy a classic "
            "personal access token with read:packages for this organization and "
            f"store it as the {CREDENTIAL_SECRET} secret in both AchaeanFleet and "
            "Telemachy.",
            status=error.status,
        ) from error
    if not isinstance(token, str) or not token:
        raise PublicationError(
            f"GHCR returned no pull token for {namespace}/{image}; the "
            f"{CREDENTIAL_SECRET} credential needs read:packages."
        )
    return token


def assert_manifest(
    *, namespace: str, image: str, tag: str, credential: str | None = None, fetch: Fetch | None = None
) -> None:
    """Assert the credential resolves one published tag."""
    fetch = fetch or default_fetch
    token = pull_token(
        namespace=namespace, image=image, credential=credential, fetch=fetch
    )
    _send(
        urllib.request.Request(
            f"{REGISTRY}/v2/{namespace}/{image}/manifests/{tag}",
            headers={"Authorization": f"Bearer {token}", "Accept": MANIFEST_ACCEPT},
            method="HEAD",
        ),
        fetch,
    )


def package_visibility(
    *, owner: str, image: str, token: str, fetch: Fetch | None = None
) -> str | None:
    """Return the reported visibility, or ``None`` when the token cannot read it.

    Read-only by design: the package must stay private, so this only records
    what GitHub reports for the published artifact.
    """
    fetch = fetch or default_fetch
    url = f"{API}/orgs/{owner}/packages/container/{image}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        visibility: Any = json.loads(_send(request, fetch)).get("visibility")
    except PublicationError as error:
        if error.status in (403, 404):
            return None
        raise
    return visibility if isinstance(visibility, str) else None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True, help="organization owning the package")
    parser.add_argument("--image", required=True, help="container image name")
    parser.add_argument(
        "--tags", nargs="+", required=True, help="published tags Telemachy consumes"
    )
    parser.add_argument(
        "--report-visibility",
        action="store_true",
        help="print the visibility GitHub reports, without changing it",
    )
    arguments = parser.parse_args(argv)
    namespace = arguments.owner.lower()
    try:
        if arguments.report_visibility:
            token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
            visibility = None
            if token:
                visibility = package_visibility(
                    owner=arguments.owner, image=arguments.image, token=token
                )
            print(f"Package visibility: {visibility or 'not readable by this token'}")
        for tag in arguments.tags:
            assert_manifest(namespace=namespace, image=arguments.image, tag=tag)
            print(f"Credential pull OK: {namespace}/{arguments.image}:{tag}")
    except PublicationError as error:
        print(f"Publication check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
