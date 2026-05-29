"""Regression tests for nomad/mesh.nomad.hcl vessel group completeness.

Validates that all 9 expected vessel groups are present and correctly configured:
- All 9 group names are present
- Each group has exactly one task block with the correct image name
- Each group declares port "agent" { to = 23001 }
- Each group has a service check with path = "/health"
- Each task has agamemnon_sidecar_path and tls_cert_dir volume mounts (:ro)
- Each task sets AGENT_PORT = "23001" and AGAMEMNON_URL = var.agamemnon_url
- Pure text/regex assertions — no nomad binary required
"""

import re
from pathlib import Path

NOMAD_JOB = Path(__file__).parent.parent / "nomad" / "mesh.nomad.hcl"

EXPECTED_GROUPS = [
    "claude-agents",
    "aider-agents",
    "codex-agents",
    "goose-agents",
    "cline-agents",
    "opencode-agents",
    "codebuff-agents",
    "ampcode-agents",
    "worker-agents",
]

# Groups whose task image name differs from the group base name
IMAGE_OVERRIDES: dict[str, str] = {}

# Groups that do not follow the standard achaean-<name>:latest image pattern
# (worker uses a separate image, claude/aider are also standard)


def _text() -> str:
    return NOMAD_JOB.read_text()


def _group_base(group_name: str) -> str:
    """Return the agent name portion from a group name (strip '-agents' suffix)."""
    return group_name.removesuffix("-agents")


def test_all_nine_groups_present() -> None:
    """All 9 expected vessel groups must be declared in mesh.nomad.hcl."""
    text = _text()
    for group in EXPECTED_GROUPS:
        assert f'group "{group}"' in text, (
            f'Group "{group}" is missing from nomad/mesh.nomad.hcl. '
            f"Expected 9 groups; found only: "
            + str([g for g in EXPECTED_GROUPS if f'group "{g}"' in text])
        )


def test_nine_groups_total() -> None:
    """Exactly 9 active (non-commented) vessel groups must be present."""
    text = _text()
    # Match only non-commented group lines
    active_groups = re.findall(r'^\s+group\s+"[a-z]+-agents"', text, re.MULTILINE)
    assert len(active_groups) == 9, (
        f"Expected 9 active group blocks, found {len(active_groups)}: {active_groups}"
    )


def test_each_group_has_correct_image() -> None:
    """Each vessel group must declare the correct achaean-<name>:latest image."""
    text = _text()
    for group in EXPECTED_GROUPS:
        name = _group_base(group)
        image = IMAGE_OVERRIDES.get(group, f"achaean-{name}:latest")
        assert f'image        = "{image}"' in text or f'image = "{image}"' in text, (
            f'Group "{group}" must declare image = "{image}" in its task config'
        )


def test_each_group_declares_agent_port_23001() -> None:
    """Every group's network block must declare port 'agent' mapped to container 23001."""
    text = _text()
    # The pattern appears once per group (except worker which also has it)
    port_declarations = re.findall(r'port\s+"agent"\s*\{\s*to\s*=\s*23001\s*\}', text)
    # We expect at least 9 (one per group; claude-agents uses the multi-line form)
    # claude-agents uses multi-line form with comment — check separately
    multiline_port = re.findall(
        r'port\s+"agent"\s*\{[^}]*to\s*=\s*23001[^}]*\}', text, re.DOTALL
    )
    assert len(multiline_port) == 9, (
        f"Expected 9 port 'agent' {{ to = 23001 }} declarations (one per group), "
        f"found {len(multiline_port)}"
    )


def test_each_group_has_agent_port_env() -> None:
    """Every task must set AGENT_PORT = '23001' in its env stanza."""
    text = _text()
    occurrences = text.count('AGENT_PORT    = "23001"') + text.count('AGENT_PORT  = "23001"') + text.count('AGENT_PORT = "23001"')
    assert occurrences >= 9, (
        f"Expected at least 9 AGENT_PORT = \"23001\" env declarations (one per group), "
        f"found {occurrences}"
    )


def test_each_group_has_agamemnon_url_env() -> None:
    """Every task must reference var.agamemnon_url for AGAMEMNON_URL."""
    text = _text()
    occurrences = text.count("AGAMEMNON_URL = var.agamemnon_url")
    assert occurrences >= 9, (
        f"Expected at least 9 AGAMEMNON_URL = var.agamemnon_url declarations, "
        f"found {occurrences}"
    )


def test_each_group_has_health_check_path() -> None:
    """Every group's service check must use path = '/health'."""
    text = _text()
    health_checks = re.findall(r'path\s*=\s*"/health"', text)
    assert len(health_checks) >= 9, (
        f"Expected at least 9 path = \"/health\" service check declarations, "
        f"found {len(health_checks)}"
    )


def test_each_group_has_agamemnon_sidecar_volume() -> None:
    """Every task must mount the agamemnon sidecar binary read-only."""
    text = _text()
    # Pattern: agamemnon_sidecar_path}:/app/agent-sidecar:ro
    sidecar_mounts = re.findall(
        r'agamemnon_sidecar_path\}:/app/agent-sidecar:ro', text
    )
    assert len(sidecar_mounts) >= 9, (
        f"Expected at least 9 agamemnon sidecar :ro volume mounts (one per group), "
        f"found {len(sidecar_mounts)}"
    )


def test_each_group_has_tls_cert_volume() -> None:
    """Every task must mount the TLS cert directory read-only."""
    text = _text()
    cert_mounts = re.findall(r'tls_cert_dir\}:/certs:ro', text)
    assert len(cert_mounts) >= 9, (
        f"Expected at least 9 tls_cert_dir :ro volume mounts (one per group), "
        f"found {len(cert_mounts)}"
    )


def test_new_groups_have_cap_drop_all() -> None:
    """The 6 new groups must enforce cap_drop = ['ALL'] for security hardening."""
    text = _text()
    new_groups = [
        "codex-agents",
        "goose-agents",
        "cline-agents",
        "opencode-agents",
        "codebuff-agents",
        "ampcode-agents",
    ]
    cap_drop_count = len(re.findall(r'cap_drop\s*=\s*\["ALL"\]', text))
    # All 9 groups should have cap_drop (3 existing + 6 new)
    assert cap_drop_count >= 9, (
        f"Expected at least 9 cap_drop = [\"ALL\"] declarations, found {cap_drop_count}. "
        f"All groups including the 6 new ones ({new_groups}) must enforce cap_drop."
    )


def test_new_groups_have_no_new_privs() -> None:
    """All groups must set no_new_privs = true for security hardening."""
    text = _text()
    no_new_privs_count = len(re.findall(r'no_new_privs\s*=\s*true', text))
    assert no_new_privs_count >= 9, (
        f"Expected at least 9 no_new_privs = true declarations, found {no_new_privs_count}"
    )


def test_six_new_groups_have_count_1() -> None:
    """The 6 new vessel groups must each have count = 1 (matching compose parity)."""
    text = _text()
    for group in [
        "codex-agents",
        "goose-agents",
        "cline-agents",
        "opencode-agents",
        "codebuff-agents",
        "ampcode-agents",
    ]:
        # Find the group block and check that count = 1 appears before the next group
        # Use a regex to extract the group block content
        pattern = re.compile(
            rf'group\s+"{re.escape(group)}"\s*\{{.*?(?=group\s+"|\Z)',
            re.DOTALL,
        )
        match = pattern.search(text)
        assert match, f'Could not locate group block for "{group}"'
        block = match.group(0)
        assert re.search(r'count\s*=\s*1\b', block), (
            f'Group "{group}" must have count = 1 (matches compose: exactly one instance)'
        )


def test_new_groups_service_naming_convention() -> None:
    """Each new group's service name must follow achaean-<name>-${NOMAD_ALLOC_INDEX}."""
    text = _text()
    for name in ["codex", "goose", "cline", "opencode", "codebuff", "ampcode"]:
        expected = f'name = "achaean-{name}-${{NOMAD_ALLOC_INDEX}}"'
        assert expected in text, (
            f'Service name for {name}-agents must be "{expected}"; not found in HCL'
        )
