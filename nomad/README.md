# Nomad deployment (Phase 6)

`nomad/mesh.nomad.hcl` manages the full heterogeneous agent mesh under Nomad.
This document covers the **secrets injection workflow** — how operators supply
API keys at runtime without committing them to the repository.

## Variables reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `agamemnon_url` | no | `http://172.20.0.1:8080` | URL of the ProjectAgamemnon coordinator |
| `agamemnon_sidecar_path` | no | `/home/mvillmow/ProjectAgamemnon/agent-sidecar/agent-sidecar` | Absolute path to the sidecar binary on the Nomad client host |
| `workspace_root` | no | `/home/mvillmow` | Absolute path to the workspace root on the Nomad client host |
| `anthropic_api_key` | **yes** | — | Anthropic API key; injected as `ANTHROPIC_API_KEY` into Claude and Aider tasks |
| `openai_api_key` | **yes** | — | OpenAI-compatible API key; injected as `OPENAI_API_KEY` into Aider tasks |

`anthropic_api_key` and `openai_api_key` have **no default** — Nomad will
refuse to run the job unless both are supplied.

## Secrets injection

Three approaches are supported, in order of preference.

### Option 1: `.nomadvar` file (recommended for local/dev)

Create a file named `secrets.nomadvar` (or any `*.nomadvar` name — Nomad loads
`*.nomadvar` automatically from the working directory, or you can pass it
explicitly with `-var-file`):

```hcl
# secrets.nomadvar  — DO NOT COMMIT THIS FILE
anthropic_api_key = "sk-ant-..."
openai_api_key    = "sk-..."
```

Run the job:

```bash
# Nomad auto-loads *.nomadvar from the working directory
nomad job run nomad/mesh.nomad.hcl

# Or pass it explicitly
nomad job run -var-file=secrets.nomadvar nomad/mesh.nomad.hcl
```

### Option 2: `-var` flags (CI/CD pipelines)

Pass each key on the command line, sourcing values from environment variables or
a secrets manager:

```bash
nomad job run \
  -var="anthropic_api_key=${ANTHROPIC_API_KEY}" \
  -var="openai_api_key=${OPENAI_API_KEY}" \
  nomad/mesh.nomad.hcl
```

This works well in GitHub Actions with repository secrets:

```yaml
- run: |
    nomad job run \
      -var="anthropic_api_key=${{ secrets.ANTHROPIC_API_KEY }}" \
      -var="openai_api_key=${{ secrets.OPENAI_API_KEY }}" \
      nomad/mesh.nomad.hcl
```

### Option 3: Vault (production)

For production clusters, use the Nomad Vault integration so the Nomad server
fetches secrets directly — no secret ever touches the operator's shell.

Each task contains a commented-out `template` block that reads from Vault.
Uncomment and adapt it, then configure the Vault paths:

| Secret | Vault path (convention) |
|---|---|
| `ANTHROPIC_API_KEY` | `secret/achaean/claude` → field `api_key` |
| `OPENAI_API_KEY` | `secret/achaean/openai` → field `api_key` |

Enable the Vault integration in the job stanza:

```hcl
vault {
  policies = ["achaean-secrets"]
}
```

The `achaean-secrets` policy must exist in your Vault instance. Create it with:

```hcl
# nomad/vault-policy.hcl — apply with: vault policy write achaean-secrets nomad/vault-policy.hcl
path "secret/data/achaean/*" {
  capabilities = ["read"]
}
```

Then uncomment the `template` block in each task and remove the `-var`
overrides — Vault becomes the sole source of truth.

## Security notes

- **Never commit API keys** to this repository in any form.
- Add `*.nomadvar` and `secrets.nomadvar` to `.gitignore` (already done in
  this repo's root `.gitignore`).
- `anthropic_api_key` and `openai_api_key` intentionally have no default — a
  misconfigured deploy fails loudly rather than silently using a wrong key.
- In production, prefer Vault over `-var` flags so keys are never visible in
  process lists or shell history.

## Example `.nomadvar` file

```hcl
# secrets.nomadvar — local dev only, never commit
anthropic_api_key = "sk-ant-api03-..."
openai_api_key    = "sk-..."

# Optional overrides (all have safe defaults)
# agamemnon_url         = "http://hermes.tailnet:8080"
# agamemnon_sidecar_path = "/opt/ProjectAgamemnon/agent-sidecar/agent-sidecar"
```

## Running the job

```bash
# Validate syntax and diff against running state
nomad job plan -var-file=secrets.nomadvar nomad/mesh.nomad.hcl

# Deploy
nomad job run -var-file=secrets.nomadvar nomad/mesh.nomad.hcl

# Monitor allocation status
nomad job status achaean-mesh

# Tail logs for a specific task
nomad alloc logs -f <alloc-id> claude
```
