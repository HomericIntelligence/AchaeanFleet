# AchaeanFleet

Container infrastructure for the HomericIntelligence agent mesh.
Builds OCI-compliant Docker images for every AI agent type.
Agent provisioning lives in [Myrmidons](../Myrmidons).

## Architecture

```
                        ┌─────────────────────────────────────────┐
                        │            AchaeanFleet images           │
                        │                                          │
  bases/                │  achaean-base-node    (Node 20 + tmux)   │
  ├─ Dockerfile.node    │  achaean-base-python  (Python 3.12)      │
  ├─ Dockerfile.python  │  achaean-base-minimal (Alpine + tmux)    │
  └─ Dockerfile.minimal │                                          │
                        │  vessels (each FROM a base):             │
  vessels/              │  achaean-claude    achaean-codex          │
  ├─ claude/            │  achaean-aider     achaean-goose          │
  ├─ codex/             │  achaean-cline     achaean-opencode       │
  ├─ aider/             │  achaean-codebuff  achaean-ampcode        │
  ├─ ...                │  achaean-worker                          │
  └─ worker/            └─────────────────────────────────────────┘
                                          │
                        Agamemnon agent sidecar mounted :ro at runtime
                                          │
                        ┌─────────────────▼────────────────────────┐
                        │           ProjectAgamemnon                │
                        │   (coordinator — manages containers)      │
                        └──────────────────────────────────────────┘
```

## Quick start

**For new developers, start with:**

```bash
git clone https://github.com/HomericIntelligence/AchaeanFleet
cd AchaeanFleet
just bootstrap   # Sets up environment: .env, Dagger dependencies, shows container runtime
```

Then edit `compose/.env` to add your API keys, and continue:

```bash
just build-all   # Build all base and vessel images
just compose-up  # Run Claude-only fleet (Phase 3)
# OR
just mesh-up     # Run full heterogeneous mesh (Phase 4)
```

**Manual setup (if you prefer):**

```bash
cp compose/.env.example compose/.env
nano compose/.env   # set ANTHROPIC_API_KEY, verify AGAMEMNON_URL
```

## Host requirements

**Claude-only fleet (Phase 3):**

- Memory: 12 GB minimum (5 Claude agents × 4G limit; practical min ~2.5 GB with reservations)
- CPU: 2 cores
- Disk: 5 GB for images

**Full heterogeneous mesh (Phase 4):**

- Memory: **50 GB hard limit** (8 AI agents × 4G + 1 worker × 1G);
  **practical minimum 8 GB** with memory reservations
- CPU: 8+ cores recommended
- Disk: 15 GB for images

Memory limits are tunable in `compose/.env` — reduce `*_MEM_LIMIT` values if your host is smaller.
Each agent reserves 512 MB (worker reserves 128 MB) to guarantee minimum responsiveness during burst load.

## Building images

```bash
# Build everything
just build-all

# Build a single vessel (builds its base first)
just build-vessel claude
just build-vessel aider

# Build via Dagger (CI parity)
just test
just push   # set REGISTRY=ghcr.io/homericintelligence or override in .env
```

## Environment variables

| Variable        | Required | Default                          | Purpose                                             |
|-----------------|----------|----------------------------------|-----------------------------------------------------|
| `CONTAINER_CMD` | No       | auto-detected (`podman`/`docker`) | Override the container binary                      |
| `TAG`           | No       | `latest`                         | Image tag applied to all built images               |
| `REGISTRY`      | No       | `ghcr.io/homericintelligence`    | Registry prefix used by `just push`                 |

**Podman users (Fedora, RHEL):** The justfile auto-detects `podman` if it is on your `PATH`.
To force a specific binary:

```bash
CONTAINER_CMD=podman just build-all
CONTAINER_CMD=podman just build-vessel claude
```

> **Note:** Podman rootless requires that volume mounts for the Agamemnon sidecar use the `:Z`
> SELinux label on SELinux-enforcing hosts. The Compose files in `compose/` already include `:Z`
> where needed.

## Port mapping

```
8080      ProjectAgamemnon coordinator (not in this repo)
23001     hi-aindrea (claude)
23002     (reserved)
23003     hi-baird (claude)
23004     hi-vegai (claude)
23010     hi-codex-1
23020     hi-aider-1
23030     hi-goose-1
23040     hi-cline-1
23050     hi-opencode-1
23060     hi-codebuff-1
23070     hi-ampcode-1
23080     hi-worker-1
```

## Secret management

API keys are kept out of `docker inspect` output and `docker compose config` by
mounting them as Docker secrets files rather than passing them as environment
variables.

### Method 1 — Docker secrets (recommended)

```bash
mkdir -p compose/secrets
# Write the key value only — no quotes, no trailing newline
echo -n "sk-ant-api03-..." > compose/secrets/anthropic_api_key
echo -n "sk-proj-..."      > compose/secrets/openai_api_key
chmod 600 compose/secrets/*
```

Each container's `entrypoint.sh` reads `/run/secrets/anthropic_api_key`
(or `openai_api_key`) and exports the value into the environment before handing off
to the agent. Leave `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` blank in `.env`.

The `compose/secrets/` directory is gitignored — only the `.gitkeep` placeholder
is committed.

### Method 2 — Encrypted secrets (SOPS or age)

For teams using secret management tools, use `scripts/load-secrets.sh`:

```bash
# Decrypt with SOPS (requires encrypted .enc files)
bash scripts/load-secrets.sh --tool sops

# Decrypt with age (requires ~/.age/key.txt and .enc files)
bash scripts/load-secrets.sh --tool age

# Load from environment variables
bash scripts/load-secrets.sh --tool env

# Clean up secrets before shutdown
bash scripts/load-secrets.sh teardown
```

See the script for configuration details: `scripts/load-secrets.sh`

### Method 3 — Plain environment variables (fallback)

Set `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` in `compose/.env`. The entrypoint
falls back to these when the secret files are absent. **Keys will be visible in
`docker inspect <container>` output** — use this only for local development when
secrets file setup is not practical.

### Security note

Docker secrets keep keys out of `docker inspect` and `docker compose config`.
The key will still appear in the child process environment after `exec` in
`entrypoint.sh`. True process-environment isolation requires each agent tool's
CLI to read the secret file directly — that is outside the scope of this repo.

### Compose file security overrides

If you use `docker-compose.override.yml` or stack multiple compose files with `-f`,
be aware that YAML merge anchors (like `<<: *security`) are **not preserved** across
file boundaries. Override files that redefine `security_opt`, `cap_drop`, or `read_only`
without repeating all keys will silently drop your security settings.

**Always verify the final config before deploying:**

```bash
docker compose -f docker-compose.mesh.yml -f docker-compose.override.yml config \
  | grep -A 2 'security_opt\|cap_drop\|read_only'
```

### Logging configuration

```bash
LOG_MAX_SIZE=50m   # max size of a single log file (default: 10m)
LOG_MAX_FILES=5    # number of rotated files to keep (default: 3)
```

> **WSL2 note:** Without log rotation, 10+ long-running containers can fill the WSL2 virtual disk
> and make the entire instance unresponsive. Never remove the `logging` block from compose services.

## Agamemnon agent sidecar

All containers expect the Agamemnon agent sidecar mounted at `/app/agent-sidecar:ro`.
The binary lives in ProjectAgamemnon and is never copied into images at build time.
Configure its path via `AGAMEMNON_URL` in `compose/.env`.

## Testing

```bash
# Validate all compose YAML files parse without errors (no images needed)
just test-compose

# Build the worker vessel, start it, probe /health on port 23080, then tear down
just test-smoke
```

`test-compose` runs `docker compose config` against each compose file and exits non-zero on any parse error.
No images are required — just Docker Compose and the repo checkout.

`test-smoke` builds `achaean-base-minimal` and `achaean-worker` locally, starts the worker via
`compose/docker-compose.smoke.yml`, polls `http://localhost:23080/health` until it responds, and tears down.
Requires Docker. Takes ~2–5 minutes on first run due to image builds.

Both checks run automatically in CI on every PR that touches `bases/**`, `vessels/**`, `compose/**`, or `dagger/**`.

## Adding a new agent type

1. Pick a base: `node`, `python`, or `minimal`
2. Create `vessels/<name>/Dockerfile` with `ARG BASE_IMAGE`
3. Add entries to `compose/docker-compose.mesh.yml` and `dagger/pipeline.ts`
4. Add `<NAME>_PROJECT=/path/to/project` to `compose/.env.example` (defines the workspace this agent mounts)
5. Add to the build matrix in `.github/workflows/ci.yml`
6. Run `just build-vessel <name>` to verify

## hephaestus/ Python utilities

The `hephaestus/` directory provides Python utilities used by CI and the test suite:

| Module | Purpose |
|--------|---------|
| `hephaestus/tags.py` | Image tag generation (`:latest`, `:git-<sha>`, `:YYYY-MM-DD-<sha>`) |
| `hephaestus/digest.py` | Docker image digest capture and validation before registry push |
| `hephaestus/tag_verify.py` | Post-push GHCR tag verification helpers |

These modules are imported by `tests/` to verify that CI pushes the expected tags to GHCR.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for Dockerfile conventions, branch strategy, and the PR
review process.

## Nomad (Phase 6)

```bash
# Validate
nomad job plan nomad/mesh.nomad.hcl

# Deploy (override defaults)
nomad job run \
  -var="agamemnon_url=http://hermes.tailnet:8080" \
  -var="agamemnon_sidecar_path=/opt/ProjectAgamemnon/agent-sidecar/agent-sidecar" \
  nomad/mesh.nomad.hcl
```

API keys (`anthropic_api_key`, `openai_api_key`) are required variables with no
default. See [`nomad/README.md`](nomad/README.md) for the full secrets injection
workflow (`.nomadvar` file, `-var` flags, and Vault).
