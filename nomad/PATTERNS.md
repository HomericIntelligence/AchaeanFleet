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

> **Note:** `mesh.nomad.hcl` currently contains this anti-pattern in the `claude-agents`,
> `aider-agents`, and `worker-agents` groups. It is tracked for correction in the Phase 6
> rework (see issue #110 / #19).

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

**Current state (Phases 1–5):**
API keys and other secrets are **not yet wired** into the Nomad job spec. When Phase 6
is implemented, secrets must be injected dynamically from Vault, never stored in HCL
or passed as plain environment variables.

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
