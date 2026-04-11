# Changelog

All notable changes to AchaeanFleet will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- Remove `NOPASSWD:ALL` sudoers entry from all 3 base Dockerfiles (`node`, `python`, `minimal`) — addresses audit finding #28
- Scope Docker Compose volume mounts from broad home-directory mounts to per-agent workspace directories — addresses audit finding #29

### Fixed
- `scripts/build-all.sh` now honours `CONTAINER_CMD` env var (defaults to `docker`), enabling podman-based builds — addresses audit finding #30

### Added
- `dagger/package-lock.json` — locked npm dependency tree for the Dagger pipeline — addresses audit finding #31
- `pixi.lock` — locked Conda/pixi environment for reproducible developer setup — addresses audit finding #31
- Hadolint step in CI (`lint` job) to catch Dockerfile issues before builds — addresses audit finding #37
- Trivy vulnerability scan step in CI for each built vessel image — addresses audit finding #37
- `CHANGELOG.md` (this file) — addresses audit finding #35
- `bootstrap` recipe in `justfile` for one-command developer environment setup — addresses audit finding #38
- `bases/common-setup.sh` shared setup script, referenced by all 3 base Dockerfiles to eliminate duplicated ~20-line apt/tmux/zsh block — addresses audit finding #33

## [0.1.0] — 2026-02-15

### Added
- Initial AchaeanFleet repository structure: `bases/`, `vessels/`, `compose/`, `nomad/`, `dagger/`
- 3 base images: `achaean-base-node`, `achaean-base-python`, `achaean-base-minimal`
- 9 vessel images: claude, codex, aider, goose, cline, opencode, codebuff, ampcode, worker
- Docker Compose files: `docker-compose.claude-only.yml` (Phase 3), `docker-compose.mesh.yml` (Phase 4)
- Dagger CI/CD pipeline (`dagger/pipeline.ts`) with build, test, and push targets
- GitHub Actions CI workflow with matrix build of all bases and vessels
- `justfile` with recipes for build, test, push, compose, and pod management
- `scripts/build-all.sh` for sequential local builds
- LICENSE (BSD 3-Clause), CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md
- ADR-006: decouple from ai-maestro, adopt homeric-mesh and AGAMEMNON_URL
