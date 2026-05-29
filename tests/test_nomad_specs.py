"""Regression tests for Nomad job spec port configuration.

Validates that all active group specs in nomad/*.nomad.hcl use:
  - to = 23001 (AGENT_PORT) on the "agent" port block (internal container port)
  - no static = <n> on the "agent" port block (host port must remain dynamic)
  - AGENT_PORT = "23001" in the task env block
  - ports = ["agent"] in the task Docker driver config

Mirrors the spirit of test_pod_specs.py for pod specs.

Follows the same text-parsing pattern as test_nomad_vault_integration.py:
no python-hcl2 dependency; regex extraction is sufficient and matches the
existing project convention for HCL audits.
"""

import re
from pathlib import Path

import pytest

NOMAD_DIR = Path(__file__).parent.parent / "nomad"
AGENT_PORT = 23001


def _extract_groups(hcl_text: str) -> list[tuple[str, str]]:
    """Extract (group_name, group_block_content) pairs from HCL job spec text.

    Handles brace-depth tracking so that nested blocks within a group are
    included in the group content.  Only non-commented group blocks are
    returned (commented-out blocks such as gpu-agents are preceded by '#' and
    will not match the regex anchor).
    """
    groups: list[tuple[str, str]] = []
    lines = hcl_text.split("\n")
    i = 0
    while i < len(lines):
        m = re.match(r'^\s*group\s+"([^"]+)"\s*\{', lines[i])
        if m:
            name = m.group(1)
            depth = 1
            start = i
            i += 1
            while i < len(lines) and depth > 0:
                for ch in lines[i]:
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                if depth == 0:
                    block = "\n".join(lines[start : i + 1])
                    groups.append((name, block))
                i += 1
            continue
        i += 1
    return groups


def _nomad_cases() -> list[tuple[str, str, str]]:
    """Yield (filename, group_name, group_content) for every active group in nomad/*.nomad.hcl."""
    cases: list[tuple[str, str, str]] = []
    for hcl_file in sorted(NOMAD_DIR.glob("*.nomad.hcl")):
        text = hcl_file.read_text()
        for group_name, group_content in _extract_groups(text):
            cases.append((hcl_file.name, group_name, group_content))
    return cases


CASES = _nomad_cases()


def test_nomad_cases_not_empty() -> None:
    """Guard: at least one (file, group) case must exist to prevent silent false passes."""
    assert len(CASES) > 0, (
        f"No Nomad group specs found in {NOMAD_DIR} — "
        "check that *.nomad.hcl files exist and contain active group blocks."
    )


@pytest.mark.parametrize("filename,group,content", CASES)
def test_container_port_is_agent_port(filename: str, group: str, content: str) -> None:
    """The 'agent' port block must set to = 23001 (internal container port)."""
    m = re.search(r'port\s+"agent"\s*\{[^}]*to\s*=\s*(\d+)', content, re.DOTALL)
    assert m is not None, (
        f"{filename}::{group}: no 'port \"agent\" {{ to = N }}' block found"
    )
    actual = int(m.group(1))
    assert actual == AGENT_PORT, (
        f"{filename}::{group}: port \"agent\" has to={actual}, expected {AGENT_PORT}"
    )


@pytest.mark.parametrize("filename,group,content", CASES)
def test_no_static_host_port(filename: str, group: str, content: str) -> None:
    """The 'agent' port block must NOT contain a static = N field (host port must be dynamic)."""
    m = re.search(r'port\s+"agent"\s*\{[^}]*\bstatic\b', content, re.DOTALL)
    assert m is None, (
        f"{filename}::{group}: port \"agent\" contains a 'static' field — "
        "host port must remain dynamic (remove the static = <n> assignment)"
    )


@pytest.mark.parametrize("filename,group,content", CASES)
def test_agent_port_env_and_ports_binding(filename: str, group: str, content: str) -> None:
    """Task must expose AGENT_PORT = '23001' in env and ports = ['agent'] in Docker config."""
    env_m = re.search(r'AGENT_PORT\s*=\s*"(\d+)"', content)
    assert env_m is not None, (
        f"{filename}::{group}: AGENT_PORT env var not found in group block"
    )
    assert env_m.group(1) == str(AGENT_PORT), (
        f"{filename}::{group}: AGENT_PORT={env_m.group(1)!r}, expected {AGENT_PORT!r}"
    )

    ports_m = re.search(r'ports\s*=\s*\["agent"\]', content)
    assert ports_m is not None, (
        f"{filename}::{group}: config.ports = [\"agent\"] not found — "
        "Docker driver must map the Nomad-allocated host port via the 'agent' label"
    )
