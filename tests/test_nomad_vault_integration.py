"""Static regex tests for Vault integration in nomad/mesh.nomad.hcl.

Validates that:
- A job-level vault {} block with the correct policy is present.
- claude-agents task has a KV v2 template stanza for ANTHROPIC_API_KEY.
- aider-agents task has a KV v2 template stanza for ANTHROPIC_API_KEY.
- All Vault template stanzas use destination = "secrets/env" and env = true.
- No KV v1 paths (missing /data/ segment) are present.
- No inline secrets (sk- prefixed keys) are present.
- All .Data. references use the KV v2 form .Data.data.<field>.
"""

import re
from pathlib import Path

NOMAD_JOB = Path(__file__).parent.parent / "nomad" / "mesh.nomad.hcl"


def _text() -> str:
    return NOMAD_JOB.read_text()


def test_job_level_vault_block_present() -> None:
    """Job must contain a vault {} block with the achaean-secrets policy."""
    text = _text()
    assert re.search(r'vault\s*\{', text), "No vault { block found in job spec"
    assert 'policies = ["achaean-secrets"]' in text, (
        'vault block must contain policies = ["achaean-secrets"]'
    )


def test_claude_agents_vault_template_path() -> None:
    """claude-agents task must reference the KV v2 path secret/data/achaean/claude."""
    text = _text()
    assert 'secret/data/achaean/claude' in text, (
        "claude-agents template must use KV v2 path: secret/data/achaean/claude"
    )


def test_claude_agents_anthropic_api_key_field() -> None:
    """claude-agents template must extract ANTHROPIC_API_KEY with correct field syntax."""
    text = _text()
    assert 'ANTHROPIC_API_KEY={{ .Data.data.anthropic_api_key }}' in text, (
        "claude-agents template must set ANTHROPIC_API_KEY={{ .Data.data.anthropic_api_key }}"
    )


def test_aider_agents_vault_template_path() -> None:
    """aider-agents task must reference the KV v2 path secret/data/achaean/aider."""
    text = _text()
    assert 'secret/data/achaean/aider' in text, (
        "aider-agents template must use KV v2 path: secret/data/achaean/aider"
    )


def test_aider_agents_anthropic_api_key_field() -> None:
    """aider-agents template must extract ANTHROPIC_API_KEY with correct field syntax."""
    text = _text()
    # Both claude and aider use the same field name — count occurrences to confirm both
    occurrences = text.count('ANTHROPIC_API_KEY={{ .Data.data.anthropic_api_key }}')
    assert occurrences >= 2, (
        f"Expected ANTHROPIC_API_KEY extraction in at least 2 template stanzas, found {occurrences}"
    )


def test_vault_templates_use_secrets_destination() -> None:
    """All Vault secret template stanzas must write to secrets/env."""
    text = _text()
    # Every occurrence of secret/data/achaean/ must be in a template that targets secrets/env
    vault_template_count = len(re.findall(r'secret/data/achaean/', text))
    secrets_env_count = text.count('destination = "secrets/env"')
    assert secrets_env_count >= vault_template_count, (
        f"Expected at least {vault_template_count} 'destination = \"secrets/env\"' stanzas, "
        f"found {secrets_env_count}"
    )


def test_vault_templates_have_env_true() -> None:
    """Vault secret template stanzas must set env = true."""
    text = _text()
    # secrets/env destination blocks must include env = true
    # We check that env = true appears at least as many times as vault secret paths
    vault_template_count = len(re.findall(r'secret/data/achaean/', text))
    env_true_count = len(re.findall(r'env\s*=\s*true', text))
    assert env_true_count >= vault_template_count, (
        f"Expected at least {vault_template_count} 'env = true' in Vault template stanzas, "
        f"found {env_true_count}"
    )


def test_no_kv1_paths() -> None:
    """No KV v1 paths (secret/<name> without /data/ segment) must be present."""
    text = _text()
    # Match secret "secret/achaean/<anything>" — missing /data/ = KV v1
    matches = re.findall(r'secret\s+"secret/achaean/', text)
    assert not matches, (
        f"Found KV v1 path(s) (missing /data/ segment): {matches}. "
        "Use secret/data/achaean/<name> instead."
    )


def test_no_inline_secrets() -> None:
    """No inline API key literals (sk- prefix) must appear in the job spec."""
    text = _text()
    matches = re.findall(r'(?i)(api[_-]?key|secret)\s*=\s*"sk-[a-zA-Z0-9]', text)
    assert not matches, f"Found inline secret(s) in job spec: {matches}"


def test_no_kv1_data_field_syntax() -> None:
    """All .Data. references must use KV v2 form (.Data.data.<field>), not bare .Data.<field>."""
    text = _text()
    # Match .Data. followed by a word that is NOT "data" (i.e. KV v1 bare field access)
    kv1_refs = re.findall(r'\.Data\.(?!data\b)\w+', text)
    assert not kv1_refs, (
        f"Found KV v1-style .Data.<field> references (should be .Data.data.<field>): {kv1_refs}"
    )
