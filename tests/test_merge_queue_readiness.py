"""Regression guards for the required-check merge-queue contract."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

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


def _load_workflows() -> dict[Path, dict]:
    """Load workflows without YAML 1.1 coercing the GitHub ``on`` key."""
    workflows: dict[Path, dict] = {}
    for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        assert isinstance(data, dict), f"Expected a mapping in {path}"
        workflows[path] = data
    return workflows


def _required_context_producers(
    workflows: dict[Path, dict],
) -> dict[str, set[Path]]:
    """Map every required context to workflows containing a matching job name."""
    producers: defaultdict[str, set[Path]] = defaultdict(set)
    for path, workflow in workflows.items():
        jobs = workflow.get("jobs", {})
        assert isinstance(jobs, dict), f"Expected jobs mapping in {path}"
        for job_id, job in jobs.items():
            assert isinstance(job, dict), f"Expected mapping for job {job_id} in {path}"
            context = job.get("name", job_id)
            if context in REQUIRED_CONTEXTS:
                producers[context].add(path)
    return producers


def test_every_required_context_has_a_workflow_producer() -> None:
    """The repository must continue emitting every live required context."""
    producers = _required_context_producers(_load_workflows())

    missing = REQUIRED_CONTEXTS - producers.keys()
    assert not missing, f"Required contexts have no workflow producer: {sorted(missing)}"


def test_required_context_workflows_support_merge_queue_and_existing_events() -> None:
    """Every required-context producer must run for PRs, main pushes, and queue groups."""
    workflows = _load_workflows()
    producers = _required_context_producers(workflows)

    producer_paths = set().union(*producers.values())
    for path in sorted(producer_paths):
        triggers = workflows[path].get("on")
        assert isinstance(triggers, dict), f"Expected event mapping in {path}"

        assert triggers.get("pull_request", {}).get("branches") == ["main"], (
            f"{path} must preserve pull_request coverage for main"
        )
        assert triggers.get("push", {}).get("branches") == ["main"], (
            f"{path} must preserve push coverage for main"
        )
        assert triggers.get("merge_group", {}).get("types") == ["checks_requested"], (
            f"{path} must run required contexts for merge_group/checks_requested"
        )
