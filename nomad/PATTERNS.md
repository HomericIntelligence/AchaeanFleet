# Nomad HCL Authoring Patterns

Reference for authoring `nomad/*.hcl` files in this repo. Read this before editing job specs.

---

## 1. Variable blocks — job-level config

Use `variable` blocks for values that change between environments (URLs, paths, counts).
Override at run time with `-var` or a `.nomadvar` file.

```hcl
variable "agamemnon_url" {
  description = "URL of the ProjectAgamemnon coordinator"
  type        = string
  default     = "http://172.20.0.1:8080"
}
```

Reference in HCL expressions with `var.<name>`:

```hcl
env {
  AGAMEMNON_URL = var.agamemnon_url
}
```

---

## 2. Template stanzas — alloc-scoped runtime values

Nomad runtime metadata (`NOMAD_ALLOC_INDEX`, `NOMAD_ALLOC_ID`, `NOMAD_JOB_NAME`, etc.)
is **only reliably available inside `template` stanzas** via Consul Template syntax.
Set `env = true` to inject the rendered key-value pairs as environment variables.

```hcl
template {
  data        = <<EOT
TMUX_SESSION_NAME="claude-{{ env "NOMAD_ALLOC_INDEX" }}"
AGENT_ID="claude-{{ env "NOMAD_ALLOC_INDEX" }}"
EOT
  destination = "local/runtime-env.env"
  env         = true
}
```

Keep static values (ports, model names, URLs from `var.*`) in the plain `env {}` stanza;
move only alloc-scoped runtime values into `template`.

---

## 3. Anti-pattern: `${VAR}` in bare `env` stanzas

**Do not do this:**

```hcl
# WRONG — NOMAD_ALLOC_INDEX is not interpolated here
env {
  TMUX_SESSION_NAME = "claude-${NOMAD_ALLOC_INDEX}"
  AGENT_ID          = "claude-${NOMAD_ALLOC_INDEX}"
}
```

Nomad's `env` stanza supports HCL expressions (`var.*`, string literals, arithmetic) but
does **not** perform Consul Template interpolation. Using `${NOMAD_ALLOC_INDEX}` in a bare
`env` block either produces the literal string `"claude-${NOMAD_ALLOC_INDEX}"` or fails
silently depending on the Nomad version and task driver.

> **Note:** This anti-pattern previously existed in `mesh.nomad.hcl` across the `claude-agents`,
> `aider-agents`, and `worker-agents` groups. It was corrected in commit 34f2128 (see issues
> #110, #19, #578). All three groups now use `template` stanzas with Consul Template syntax
> as shown in § 2 above. The 6 Phase 6 vessel groups (`codex-agents`, `gemini-agents`,
> `goose-agents`, `opencode-agents`, `q-agents`, `agentcode-agents`) are tracked in issue #577.

---

## 4. Valid HCL interpolation in non-`env` stanzas

`${NOMAD_ALLOC_INDEX}` **is** valid HCL in `service.name`, `config`, and other stanzas
that are evaluated as HCL expressions (not Consul Template). Leave these as-is.

```hcl
service {
  name = "achaean-claude-${NOMAD_ALLOC_INDEX}"  # correct — HCL context
  port = "agent"
}
```

---

## 5. Secrets Management (Phase 6 Vault Integration)

**Current state:**
Secrets are wired for claude and aider groups in `mesh.nomad.hcl`; see the
`vault { policies = ["achaean-secrets"] }` job stanza and per-group `template` stanzas.
Secrets must be injected dynamically from Vault — never stored in HCL or passed as
plain environment variables.

**When implementing (Phase 6+):**

Use the `template` stanza with Consul Template and Vault backend to fetch secrets at
allocation time:

```hcl
template {
  data = <<EOH
{{ with secret "secret/data/homeric/api-keys" }}
ANTHROPIC_API_KEY={{ .Data.data.anthropic_api_key }}
{{ end }}
EOH
  destination = "secrets/env"
  env         = true
}
```

**Key rules:**

- **Never use inline env vars** for secrets (`env { ANTHROPIC_API_KEY = "sk-..." }`)
- **Never store secrets in HCL** or `.nomadvar` files
- **Always use `template` with Vault backend** for dynamic secret injection
- Vault path format: `secret/data/<mount>/<secret-name>` (the `/data/` segment is required)
- Retrieve fields via `{{ .Data.data.<field-name> }}` (Consul Template syntax)

**Comparison with Docker Compose:**
The Compose approach uses `secrets` blocks (Docker Secrets or Swarm) or environment
files with restricted permissions. The Nomad approach is equivalent: Vault provides the
secret store, and the `template` stanza injects them into the allocation's environment
at runtime. Both keep secrets out of the image and configuration-as-code.

**Phases 1–5 workaround (if needed temporarily):**
For development/testing before Vault is available, you may temporarily pass secrets
via Nomad variable overrides (e.g., `-var="anthropic_api_key=sk-..."` at `nomad job run`
time). This is acceptable only for dev/test; **production deployments must use Vault**.

---

## 6. Overriding container ENTRYPOINT and command in Nomad

When you need to override a Docker image's `ENTRYPOINT` or `CMD` in Nomad, use the
`config` stanza in the task. This is useful for injecting custom startup scripts,
debugging, or running alternative entry points.

**Key fields:**

- `entrypoint` — array replacing the image's `ENTRYPOINT` instruction
- `args` — array replacing the image's `CMD` instruction
- `command` — NOT the same as `cmd`; use `entrypoint` + `args` instead

```hcl
task "claude" {
  driver = "docker"
  config {
    image      = "achaean-claude:latest"
    # Override ENTRYPOINT — use this to inject a custom startup script
    entrypoint = ["/bin/sh", "/tmp/custom-init.sh"]
    args       = []
  }
}
```

To run a shell command interactively (useful for debugging), use:

```hcl
config {
  image      = "achaean-claude:latest"
  entrypoint = ["/bin/sh", "-c"]
  args       = ["echo 'Debug mode' && exec /app/start.sh"]
}
```

**Note:** Do not use bare `command` in the `config` stanza — the Docker driver
interprets `config { command }` as a shorthand for `entrypoint + args` concatenation,
which is often not what you intend. Always use `entrypoint` and `args` separately for clarity.

---

## Quick reference — commonly needed Nomad runtime variables

| Variable | Description |
|---|---|
| `NOMAD_ALLOC_INDEX` | 0-based index of this alloc within the group |
| `NOMAD_ALLOC_ID` | UUID of this allocation |
| `NOMAD_JOB_NAME` | Job name |
| `NOMAD_GROUP_NAME` | Group name |
| `NOMAD_TASK_NAME` | Task name |
| `NOMAD_PORT_<label>` | Dynamic host port for the named network port |
| `NOMAD_IP_<label>` | Host IP for the named network port |

All of these require Consul Template syntax (`{{ env "VAR" }}`) inside a `template` stanza.

---

## Capability validation

The `claude` task in `mesh.nomad.hcl` runs with `cap_drop=["ALL"]` and `no_new_privs=true`.
This was validated in issue #305: `claude --version` exits 0 under `--cap-drop=ALL
--security-opt=no-new-privileges` with an empty `cap_add` list.

To re-validate after a Claude Code CLI upgrade:

```bash
scripts/validate_claude_caps.sh
```

The script writes `cap_validation_report.json` with `version_check`, `cap_drop`, `cap_add`,
`failure_class`, and a `stderr` field. Pass criteria: `version_check == "pass"` and
`cap_add == []`. If caps are required, each entry must be documented with a justification
comment in `mesh.nomad.hcl` citing the specific failure observed.

See `tests/test_cap_validate.py` for unit tests of the failure-classification logic and
an integration test (`RUN_INTEGRATION=1 pytest tests/test_cap_validate.py -m integration`).
