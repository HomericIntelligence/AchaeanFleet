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

## Container startup behavior

All base images ship with `/usr/local/bin/entrypoint.sh` as the `ENTRYPOINT`. The
script runs in order:

1. **tmux session** — starts a detached tmux session named `$TMUX_SESSION_NAME`
   (default: `agent-session`). Skipped silently if tmux is unavailable or the
   session already exists.
2. **agent-server.js** — if `/app/agent-server.js` is present (bind-mounted at
   runtime by the Agamemnon agent sidecar), it is exec'd with any extra arguments
   passed to the container.
3. **explicit args** — if extra arguments were passed (`docker run <image> <cmd>`
   or compose `command:`), they are exec'd directly. This means compose overrides
   work without touching `ENTRYPOINT`.
4. **fallback shell** — if none of the above apply, `bash` is exec'd. Use
   `docker run -it <image>` for interactive access.

Every path uses `exec` so the launched process inherits PID 1 and receives
`SIGTERM`/`SIGINT` from Docker correctly.

### Examples

```bash
# Default: starts agent-server.js when bind-mounted, otherwise drops to bash
docker run achaean-claude:latest

# Interactive shell (no agent-server.js mounted)
docker run -it achaean-claude:latest

# Run an explicit command (overrides fallback but not agent-server.js check)
docker run achaean-claude:latest node /some/other/script.js

# Compose: no changes required — existing command: directives still work
```

## Agamemnon agent sidecar

All containers expect the Agamemnon agent sidecar mounted at `/app/agent-sidecar:ro`.
The binary lives in ProjectAgamemnon and is never copied into images at build time.
Configure its path via `AGAMEMNON_URL` in `compose/.env`.

## Adding a new agent type

1. Pick a base: `node`, `python`, or `minimal`
2. Create `vessels/<name>/Dockerfile` with `ARG BASE_IMAGE`
3. Add entries to `compose/docker-compose.mesh.yml` and `dagger/pipeline.ts`
4. Add to the build matrix in `.github/workflows/ci.yml`
5. Run `just build-vessel <name>` to verify

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
