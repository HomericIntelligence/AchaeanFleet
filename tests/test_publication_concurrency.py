"""Regression guards for issue #785: publication runs must not cancel.

The workflow accepted both a ``push`` and a ``workflow_run`` entry point while
keying its concurrency group on the commit SHA with ``cancel-in-progress:
true``. Same-SHA events therefore shared one group, so the second entry point
cancelled the first -- including runs already publishing to GHCR (main
``241fb0a``: runs 42749679071 and 42749696565 both ``cancelled``).

The contract encoded here is: exactly one publication entry point, a
concurrency group scoped by event name, and cancellation limited to
pull-request validation. Helpers fail closed on expression shapes they do not
understand so a future rewrite cannot quietly reintroduce the race.

Run locally:
    pixi run pytest tests/test_publication_concurrency.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

PUBLISHER_JOBS = ("push-to-registry", "push-bases", "verify-registry")
KNOWN_EVENTS = ("push", "pull_request", "schedule", "workflow_dispatch")
NON_CANCELLABLE_EVENTS = ("push", "schedule", "workflow_dispatch")

# Context values the group expression is allowed to read; anything else means
# this test can no longer prove which events can collide and must fail.
ALLOWED_GROUP_ATOMS = frozenset(
    {"github.workflow", "github.event_name", "github.head_ref", "github.sha"}
)
EVENT_COMPARISON = re.compile(
    r"\A\$\{\{\s*github\.event_name\s*==\s*'([a-z_]+)'\s*\}\}\Z"
)


def _workflow() -> dict:
    """Load ci.yml without YAML 1.1 coercing the ``on`` key."""
    if not CI_WORKFLOW.exists():
        pytest.fail(f"Workflow file not found: {CI_WORKFLOW}")
    data = yaml.load(CI_WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(data, dict), f"Expected a mapping in {CI_WORKFLOW}"
    return data


def _concurrency() -> dict:
    block = _workflow().get("concurrency")
    assert isinstance(block, dict), "ci.yml must declare a workflow-level concurrency block"
    return block


def _expanded_group(event: str, *, sha: str, head_ref: str = "") -> str:
    """Render the concurrency group for one event/SHA pair.

    Only the expression atoms in ``ALLOWED_GROUP_ATOMS`` are evaluated; an
    unknown atom fails the test rather than silently producing a group that
    looks unique.
    """
    raw = _concurrency()["group"]
    match = re.fullmatch(r"\$\{\{\s*(?P<expr>.+?)\s*\}\}", raw)
    assert match is not None, f"Unsupported concurrency group expression: {raw!r}"
    expr: str = match["expr"]

    unknown = set(re.findall(r"github\.[a-z_]+", expr)) - ALLOWED_GROUP_ATOMS
    assert not unknown, f"Concurrency group reads unsupported contexts: {sorted(unknown)}"

    rendered = (
        expr.replace("github.workflow", "Build All Agent Images")
        .replace("github.event_name", event)
        .replace("github.head_ref", head_ref)
        .replace("github.sha", sha)
    )
    return next(
        (part.strip() for part in rendered.split("||") if part.strip() not in ("", "''")),
        "",
    )


def _cancels(event: str) -> bool:
    """Evaluate cancel-in-progress for one event, failing closed on unknowns."""
    raw = _concurrency()["cancel-in-progress"]
    match = EVENT_COMPARISON.fullmatch(raw)
    if match is None:
        pytest.fail(
            "cancel-in-progress must be a single github.event_name comparison, "
            f"got {raw!r}"
        )
    return event == match[1]


def test_workflow_run_is_not_a_second_entry_point() -> None:
    triggers = set(_workflow()["on"])
    assert "workflow_run" not in triggers, (
        "workflow_run duplicates the push publisher: its github.sha is the "
        "default-branch tip rather than the scanned commit, and it shares the "
        "push run's concurrency group."
    )
    assert triggers == {"push", "pull_request", "schedule", "workflow_dispatch"}


@pytest.mark.parametrize("event", KNOWN_EVENTS)
def test_concurrency_group_is_scoped_by_event(event: str) -> None:
    group = _expanded_group(event, sha="a" * 40)
    assert event in group, f"group {group!r} does not isolate event {event!r}"


def test_same_sha_events_never_share_a_group() -> None:
    sha = "b" * 40
    groups = {_expanded_group(event, sha=sha) for event in KNOWN_EVENTS}
    assert len(groups) == len(KNOWN_EVENTS), f"same-SHA events collapsed into {groups}"


@pytest.mark.parametrize("event", NON_CANCELLABLE_EVENTS)
def test_publication_events_are_never_cancelled(event: str) -> None:
    assert _cancels(event) is False, f"{event} could cancel a publishing run"


def test_pull_request_validation_remains_cancellable() -> None:
    assert _cancels("pull_request") is True


@pytest.mark.parametrize("job_id", PUBLISHER_JOBS)
def test_publication_is_gated_on_a_single_event(job_id: str) -> None:
    job = _workflow()["jobs"][job_id]
    condition = job["if"]
    assert "workflow_run" not in condition, f"{job_id} still accepts the removed entry point"
    assert "github.event_name == 'push'" in condition, f"{job_id} is not gated on push"
