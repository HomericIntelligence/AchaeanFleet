"""Regression tests for pod spec port configuration.

Validates that all pod specs in pods/ use containerPort: 23001 (AGENT_PORT)
and only vary hostPort per the CLAUDE.md port mapping convention.
"""

from pathlib import Path

import pytest
import yaml

PODS_DIR = Path(__file__).parent.parent / "pods"
AGENT_PORT = 23001

EXPECTED_HOST_PORTS = {
    "claude-pod.yaml": 23001,
    "worker-pod.yaml": 23080,
}


def pod_specs() -> list[tuple[str, dict]]:
    return [(p.name, yaml.safe_load(p.read_text())) for p in sorted(PODS_DIR.glob("*-pod.yaml"))]


@pytest.mark.parametrize("filename,spec", pod_specs())
def test_container_port_is_agent_port(filename: str, spec: dict) -> None:
    """All containers must listen on AGENT_PORT internally."""
    for container in spec["spec"]["containers"]:
        for port in container.get("ports", []):
            assert port["containerPort"] == AGENT_PORT, (
                f"{filename}: container '{container['name']}' has "
                f"containerPort={port['containerPort']}, expected {AGENT_PORT}"
            )


@pytest.mark.parametrize("filename,spec", pod_specs())
def test_host_port_matches_convention(filename: str, spec: dict) -> None:
    """hostPort must match the CLAUDE.md port mapping table."""
    if filename not in EXPECTED_HOST_PORTS:
        pytest.skip(f"No expected hostPort defined for {filename}")
    expected = EXPECTED_HOST_PORTS[filename]
    for container in spec["spec"]["containers"]:
        for port in container.get("ports", []):
            assert port["hostPort"] == expected, (
                f"{filename}: hostPort={port['hostPort']}, expected {expected}"
            )
