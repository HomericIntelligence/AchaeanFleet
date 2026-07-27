"""Regression guards for the required-check merge-queue contract."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Live ``homeric-main-baseline`` required contexts inspected for issue #722.
REQUIRED_CONTEXTS = {
    "build",
    "deps/version-sync",
    "install",
    "integration-tests",
    "lint",
    "package",
    "release",
    "schema-validation",
    "security/dependency-scan",
    "security/secrets-scan",
    "test",
    "unit-tests",
}

MERGE_GATE_CONTEXT = "merge-gate"
FULL_REQUIRED_EVENTS = frozenset({"pull_request", "push"})
MERGE_QUEUE_SMOKE_WORKFLOW = WORKFLOWS_DIR / "merge-queue-smoke.yml"

EVENT_NAME_COMPARISON = re.compile(
    r"\A\s*github\.event_name\s*(?P<operator>==|!=)\s*(['\"])(?P<event>[^'\"]+)\2\s*\Z"
)


def _load_workflows() -> dict[Path, dict]:
    """Load workflows without YAML 1.1 coercing the GitHub ``on`` key."""
    workflows: dict[Path, dict] = {}
    for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        assert isinstance(data, dict), f"Expected a mapping in {path}"
        workflows[path] = data
    return workflows


def _context_producers(
    workflows: dict[Path, dict], contexts: frozenset[str]
) -> dict[str, list[tuple[Path, str, dict]]]:
    """Map each of ``contexts`` to its workflow path, job ID, and definition."""
    producers: defaultdict[str, list[tuple[Path, str, dict]]] = defaultdict(list)
    for path, workflow in workflows.items():
        jobs = workflow.get("jobs", {})
        assert isinstance(jobs, dict), f"Expected jobs mapping in {path}"
        for job_id, job in jobs.items():
            assert isinstance(job, dict), f"Expected mapping for job {job_id} in {path}"
            context = job.get("name", job_id)
            if context in contexts:
                producers[context].append((path, job_id, job))
    return producers


def _required_context_producers(
    workflows: dict[Path, dict],
) -> dict[str, list[tuple[Path, str, dict]]]:
    """Map every required context to its workflow path, job ID, and definition."""
    return _context_producers(workflows, frozenset(REQUIRED_CONTEXTS))


def _job_condition_allows_full_required_events(condition: str) -> bool:
    """Return whether a condition is safe for every full-matrix event.

    This intentionally accepts only a standalone direct comparison. GitHub
    expressions involving any other context, function, output, or boolean
    combination are not statically proven safe and must fail closed.
    """
    comparison = EVENT_NAME_COMPARISON.fullmatch(condition)
    if comparison is None:
        return False

    if comparison["operator"] == "==":
        return FULL_REQUIRED_EVENTS <= {comparison["event"]}
    return comparison["event"] not in FULL_REQUIRED_EVENTS


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        pytest.param(
            "github.event_name == 'merge_group'",
            False,
            id="direct-merge-group-equality",
        ),
        pytest.param(
            "github.event_name == 'push'",
            False,
            id="direct-push-equality",
        ),
        pytest.param(
            'github.event_name != "pull_request"',
            False,
            id="direct-pull-request-exclusion",
        ),
        pytest.param(
            "github.event_name == 'pull_request'",
            False,
            id="direct-pull-request-equality",
        ),
        pytest.param(
            "github.event_name != 'merge_group'",
            True,
            id="direct-merge-group-exclusion",
        ),
        pytest.param(
            "github.event_name != 'push'",
            False,
            id="direct-push-exclusion",
        ),
        pytest.param(
            "github.event_name != 'workflow_dispatch'",
            True,
            id="direct-unrelated-event-exclusion",
        ),
        pytest.param(
            "github.ref == 'refs/heads/main'",
            False,
            id="ref-expression",
        ),
        pytest.param(
            "github.event.pull_request.draft == false",
            False,
            id="pull-request-payload-expression",
        ),
        pytest.param("always()", False, id="helper-expression"),
        pytest.param(
            "needs.reusable-check.outputs.safe == 'true'",
            False,
            id="reusable-workflow-expression",
        ),
    ],
)
def test_job_condition_allows_full_required_events_is_fail_closed(
    condition: str,
    expected: bool,
) -> None:
    """Only direct event checks proven safe for PR and push may pass."""
    assert _job_condition_allows_full_required_events(condition) is expected


def test_every_required_context_has_a_workflow_producer() -> None:
    """The repository must continue emitting every live required context."""
    producers = _required_context_producers(_load_workflows())

    missing = REQUIRED_CONTEXTS - producers.keys()
    assert not missing, (
        f"Required contexts have no workflow producer: {sorted(missing)}"
    )


def test_security_events_write_is_scoped_to_security_secrets_scan() -> None:
    """Only the secrets scan may write Security-events during required runs."""
    workflow = _load_workflows()[WORKFLOWS_DIR / "_required.yml"]

    assert workflow["permissions"] == {"contents": "read"}

    jobs = workflow["jobs"]
    assert jobs["security-secrets-scan"]["permissions"] == {
        "contents": "read",
        "security-events": "write",
    }
    assert all(
        "security-events" not in job.get("permissions", {})
        for job_id, job in jobs.items()
        if job_id != "security-secrets-scan"
    )


def test_required_context_producer_discovery_retains_job_conditions() -> None:
    """Producer discovery must preserve the job definition used for gating checks."""
    path = Path("conditioned-required-check.yml")
    job = {
        "name": "lint",
        "if": "github.event_name == 'pull_request'",
        "runs-on": "ubuntu-latest",
    }
    workflows = {path: {"jobs": {"lint-job": job}}}

    producers = _required_context_producers(workflows)

    assert producers["lint"] == [(path, "lint-job", job)]


@pytest.mark.parametrize(
    "condition",
    sorted(
        {
            "github.event_name == 'pull_request'",
            "github.event_name == 'push'",
            "github.event_name == 'merge_group'",
            "github.event_name != 'merge_group'",
            "github.event_name != 'pull_request'",
            "github.event_name != 'push'",
        }
    ),
)
def test_required_job_condition_cannot_exclude_full_required_events(
    monkeypatch: pytest.MonkeyPatch,
    condition: str,
) -> None:
    """A trigger cannot compensate for a job condition that skips PR or push."""
    path = Path("conditioned-required-check.yml")
    workflows = {
        path: {
            "on": {
                "pull_request": {"branches": ["main"]},
                "push": {"branches": ["main"]},
                "merge_group": {"types": ["checks_requested"]},
            },
            "jobs": {
                "lint-job": {
                    "name": "lint",
                    "if": condition,
                }
            },
        }
    }
    monkeypatch.setitem(globals(), "_load_workflows", lambda: workflows)

    with pytest.raises(AssertionError):
        test_required_context_workflows_and_merge_queue_smoke_are_disjoint()


def test_required_context_workflow_graph_rejects_duplicate_integration_tests_producer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second valid producer must fail the executable workflow-graph guard."""
    workflows = _load_workflows()
    # Inject only into the in-memory graph; do not write a workflow file.
    duplicate_workflows = {
        **workflows,
        Path("duplicate-required-check.yml"): {
            "on": {
                "pull_request": {"branches": ["main"]},
                "push": {"branches": ["main"]},
                "merge_group": {"types": ["checks_requested"]},
            },
            "jobs": {
                "integration-tests-copy": {
                    "name": "integration-tests",
                    "runs-on": "ubuntu-latest",
                }
            },
        },
    }
    monkeypatch.setitem(globals(), "_load_workflows", lambda: duplicate_workflows)

    with pytest.raises(AssertionError, match="duplicate.*integration-tests"):
        test_required_context_workflows_and_merge_queue_smoke_are_disjoint()


def test_required_context_workflows_and_merge_queue_smoke_are_disjoint() -> None:
    """Keep the full matrix on PR/push and one fast gate on queue groups."""
    workflows = _load_workflows()
    producers = _required_context_producers(workflows)

    duplicate_producers = {
        context: [
            (path, job_id)
            for path, job_id, _job in context_producers
        ]
        for context, context_producers in producers.items()
        if len(context_producers) > 1
    }
    assert not duplicate_producers, (
        "Required contexts must have exactly one workflow producer; "
        f"duplicates: {duplicate_producers}"
    )

    for context, context_producers in sorted(producers.items()):
        for path, job_id, job in context_producers:
            condition = job.get("if")
            if condition is None:
                continue
            assert isinstance(condition, str), (
                f"Expected string condition for {job_id} in {path}"
            )
            assert _job_condition_allows_full_required_events(condition), (
                f"{path} job {job_id} ({context}) condition {condition!r} "
                "must allow pull_request and push events"
            )

    producer_paths = {
        path
        for context_producers in producers.values()
        for path, _job_id, _job in context_producers
    }
    for path in sorted(producer_paths):
        triggers = workflows[path].get("on")
        assert isinstance(triggers, dict), f"Expected event mapping in {path}"

        assert triggers.get("pull_request", {}).get("branches") == ["main"], (
            f"{path} must preserve pull_request coverage for main"
        )
        assert triggers.get("push", {}).get("branches") == ["main"], (
            f"{path} must preserve push coverage for main"
        )
        assert "merge_group" not in triggers, (
            f"{path} must leave merge_group to the fast merge-gate workflow"
        )

    smoke = workflows[MERGE_QUEUE_SMOKE_WORKFLOW]
    smoke_triggers = smoke.get("on")
    assert isinstance(smoke_triggers, dict), "Expected an event mapping in merge-queue smoke"
    assert smoke_triggers.get("merge_group", {}).get("types") == ["checks_requested"], (
        "merge-queue smoke must run for merge_group/checks_requested"
    )
    assert "pull_request" not in smoke_triggers
    assert "push" not in smoke_triggers

    merge_gate_producers = [
        (path, job_id)
        for path, workflow in workflows.items()
        if "merge_group" in workflow.get("on", {})
        for job_id, job in workflow.get("jobs", {}).items()
        if job.get("name", job_id) == MERGE_GATE_CONTEXT
    ]
    assert merge_gate_producers == [(MERGE_QUEUE_SMOKE_WORKFLOW, "merge-gate")], (
        "merge_group must emit exactly one merge-gate context"
    )
