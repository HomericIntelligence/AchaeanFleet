# AchaeanFleet Image Size Tracking

This document records image sizes at key milestones to audit the impact of
base image refactoring (issue #51) and detect future regressions.

## How to measure

```bash
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | grep achaean
```

## Base Images

The three base Dockerfiles provide foundational images from which all vessel agents are built:

- **achaean-base-minimal** — Debian bookworm-slim + Node.js 20 + tmux + zsh + git
  - Used by: goose, opencode, worker (binary-based agents)
- **achaean-base-node** — Node.js 25-slim + tmux + zsh + git
  - Used by: claude, codex, cline, codebuff, ampcode (Node.js agents)
- **achaean-base-python** — Python 3.12-slim + Node.js 20 + tmux + zsh + git
  - Used by: aider (Python agent)

## Baseline (pre-refactor, estimated from debian/python/node:*-slim + tool installs)

| Image | Estimated Pre-Refactor Size |
|-------|---------------------------|
| achaean-base-minimal | ~350 MB |
| achaean-base-node | ~400 MB |
| achaean-base-python | ~500 MB |
| achaean-goose | ~550 MB |
| achaean-opencode | ~550 MB |
| achaean-worker | ~550 MB |
| achaean-claude | ~450 MB |
| achaean-codex | ~450 MB |
| achaean-cline | ~450 MB |
| achaean-codebuff | ~450 MB |
| achaean-ampcode | ~450 MB |
| achaean-aider | ~550 MB |

## Post-refactor targets (issue #51 success criterion: ≥50 MB reduction)

| Image | Target | Status |
|-------|--------|--------|
| achaean-base-minimal | ≤300 MB | Unverified — no CI size check |
| achaean-base-node | ≤350 MB | Unverified — no CI size check |
| achaean-base-python | ≤450 MB | Unverified — no CI size check |
| achaean-goose | ≤500 MB | Unverified — no CI size check |
| achaean-opencode | ≤500 MB | Unverified — no CI size check |
| achaean-worker | ≤500 MB | Unverified — no CI size check |
| achaean-claude | ≤400 MB | Unverified — no CI size check |
| achaean-codex | ≤400 MB | Unverified — no CI size check |
| achaean-cline | ≤400 MB | Unverified — no CI size check |
| achaean-codebuff | ≤400 MB | Unverified — no CI size check |
| achaean-ampcode | ≤400 MB | Unverified — no CI size check |
| achaean-aider | ≤500 MB | Unverified — no CI size check |

## Recorded measurements

To record a measurement, add an entry below with the date, Docker build command used, and the resulting size:

```bash
# Example command (adjust base image as needed)
docker build -f bases/Dockerfile.minimal -t achaean-base-minimal:test .
docker images --format "{{.Repository}}\t{{.Tag}}\t{{.Size}}" | grep achaean-base-minimal
```

### Base Images

| Date | Image | Size | Build Context | Notes |
|------|-------|------|---------------|-------|
| — | achaean-base-minimal | — | — | Awaiting initial measurement |
| — | achaean-base-node | — | — | Awaiting initial measurement |
| — | achaean-base-python | — | — | Awaiting initial measurement |

### Vessel Images

| Date | Image | Size | Build Context | Notes |
|------|-------|------|---------------|-------|
| — | achaean-goose | — | — | Awaiting initial measurement |
| — | achaean-opencode | — | — | Awaiting initial measurement |
| — | achaean-worker | — | — | Awaiting initial measurement |
| — | achaean-claude | — | — | Awaiting initial measurement |
| — | achaean-codex | — | — | Awaiting initial measurement |
| — | achaean-cline | — | — | Awaiting initial measurement |
| — | achaean-codebuff | — | — | Awaiting initial measurement |
| — | achaean-ampcode | — | — | Awaiting initial measurement |
| — | achaean-aider | — | — | Awaiting initial measurement |

## Notes

- Actual sizes vary by Docker layer cache state and base image updates (e.g., Debian security patches, Node.js/Python point releases).
- To record a new measurement:
  1. Build the image locally: `docker build -f <dockerfile> -t achaean-<name>:test .` (or `npx ts-node dagger/pipeline.ts build`)
  2. Get the size: `docker images achaean-<name> --format "{{.Size}}"`
  3. Add a dated row to the tables above with the actual size, build date, and any relevant context
- Size checks are not currently automated in CI. Consider adding a size-gate job (e.g., `dagger/pipeline.ts` size assertion step) to enforce post-refactor targets.
- Layer analysis: use `docker history <image>` to identify layers contributing most to final size.
