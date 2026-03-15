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
                        agent-server.js mounted :ro at runtime
                                          │
                        ┌─────────────────▼────────────────────────┐
                        │             ai-maestro                    │
                        │   (orchestrator — manages containers)     │
                        └──────────────────────────────────────────┘
```

## Quick start

```bash
# 1. Clone and set up environment
git clone https://github.com/HomericIntelligence/AchaeanFleet
cd AchaeanFleet
cp compose/.env.example compose/.env
nano compose/.env   # set ANTHROPIC_API_KEY, verify AIM_HOST and AGENT_SERVER_JS

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
23000     ai-maestro dashboard (not in this repo)
23001     aim-aindrea (claude)
23002     (reserved)
23003     aim-baird (claude)
23004     aim-vegai (claude)
23010     aim-codex-1
23020     aim-aider-1
23030     aim-goose-1
23040     aim-cline-1
23050     aim-opencode-1
23060     aim-codebuff-1
23070     aim-ampcode-1
23080     aim-worker-1
```

## agent-server.js

All containers expect `agent-server.js` mounted at `/app/agent-server.js:ro`.
The source lives in ai-maestro and is never copied into images at build time.
Configure its path via `AGENT_SERVER_JS` in `compose/.env`.

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
  -var="aim_host=http://hermes.tailnet:23000" \
  -var="agent_server_path=/opt/ai-maestro/agent-container/agent-server.js" \
  nomad/mesh.nomad.hcl
```
