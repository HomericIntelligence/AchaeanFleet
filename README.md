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

```bash
# 1. Clone and set up environment
git clone https://github.com/HomericIntelligence/AchaeanFleet
cd AchaeanFleet
cp compose/.env.example compose/.env
nano compose/.env   # set ANTHROPIC_API_KEY, verify AGAMEMNON_URL

# 2. Build all images
just build-all

# 3a. Run Claude-only fleet (Phase 3)
just compose-up

# 3b. Run full heterogeneous mesh (Phase 4)
just mesh-up
```

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
LOG_MAX_SIZE=50m   # max size of a single log file (default: 10m)
LOG_MAX_FILES=5    # number of rotated files to keep (default: 3)
```

> **WSL2 note:** Without log rotation, 10+ long-running containers can fill the WSL2 virtual disk
> and make the entire instance unresponsive. Never remove the `logging` block from compose services.

Each container's `entrypoint.sh` reads `/run/secrets/anthropic_api_key` (or
`openai_api_key`) and exports the value into the environment before handing off
to the agent. Leave `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` blank in `.env`.

The `compose/secrets/` directory is gitignored — only the `.gitkeep` placeholder
is committed.

### Method 2 — Plain environment variables (fallback)

Set `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` in `compose/.env`. The entrypoint
falls back to these when the secret files are absent. **Keys will be visible in
`docker inspect <container>` output** — use this only for local development when
secrets file setup is not practical.

### Security note

Docker secrets keep keys out of `docker inspect` and `docker compose config`.
The key will still appear in the child process environment after `exec` in
`entrypoint.sh`. True process-environment isolation requires each agent tool's
CLI to read the secret file directly — that is outside the scope of this repo.

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
4. Add to the build matrix in `.github/workflows/ci.yml`
5. Run `just build-vessel <name>` to verify

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for Dockerfile conventions, branch strategy, and the PR
review process. Changes are documented in [CHANGELOG.md](CHANGELOG.md).

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
