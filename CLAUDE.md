# AchaeanFleet

Container infrastructure for the HomericIntelligence agent mesh.

## What this repo is

AchaeanFleet builds OCI-compliant Docker images for each AI agent type supported by the mesh. It is **infrastructure only** — no agent logic, no ai-maestro modifications.

## What this repo is NOT

- Do not add agent provisioning logic here → that's Myrmidons
- Do not modify ai-maestro source → it is mounted read-only via volume
- Do not add authentication, routing, or orchestration → ai-maestro handles that

## Structure

```
bases/          3 base Dockerfiles (node, python, minimal)
vessels/        9 agent vessel Dockerfiles (FROM a base + AI tool)
compose/        Docker Compose files (claude-only and full mesh)
nomad/          Nomad job specs (Phase 6)
dagger/         Dagger pipeline for CI/CD (Phase 5)
.github/        GitHub Actions CI
```

## Building images locally

```bash
# Build a base image
docker build -f bases/Dockerfile.node -t achaean-base-node:latest .

# Build a vessel (must build base first)
docker build -f vessels/claude/Dockerfile \
  --build-arg BASE_IMAGE=achaean-base-node:latest \
  -t achaean-claude:latest .

# Build all images (Phase 5+)
npx ts-node dagger/pipeline.ts build
```

## Running the mesh

```bash
# Set up environment
cd compose
cp .env.example .env
# Edit .env: add ANTHROPIC_API_KEY and verify AIM_HOST

# Claude-only (Phase 3 target)
docker compose -f docker-compose.claude-only.yml up -d

# Full heterogeneous mesh (Phase 4 target)
docker compose -f docker-compose.mesh.yml up -d
```

## Agent-server.js integration

The base images are designed to work with ai-maestro's `agent-server.js`. The file is mounted at runtime:

```yaml
volumes:
  - /home/mvillmow/ai-maestro/agent-container/agent-server.js:/app/agent-server.js:ro
```

**Never copy agent-server.js into the image at build time** — this would lock the image to a specific ai-maestro version.

## Port mapping convention

```
23000     ai-maestro dashboard (existing, not in this repo)
23001     aim-aindrea (claude)
23002     (reserved)
23003     aim-baird (claude)
23004     aim-vegai (claude)
23005     (reserved)
23010     aim-codex-1
23020     aim-aider-1
23030     aim-goose-1
23040     aim-cline-1
23050     aim-opencode-1
23060     aim-codebuff-1
23070     aim-ampcode-1
23080     aim-worker-1
```

## Network

All containers join the `aimaestro-mesh` bridge network. Containers resolve each other by service name via Docker's internal DNS. ai-maestro on the host connects via `172.20.0.1` (the Docker bridge gateway).

## Adding a new agent type

1. Choose a base image (`node`, `python`, or `minimal`)
2. Create `vessels/<agentname>/Dockerfile` with `ARG BASE_IMAGE` + install step
3. Add an entry to `compose/docker-compose.mesh.yml`
4. Add to the matrix in `.github/workflows/ci.yml`
5. Add vessel entry in `dagger/pipeline.ts`
