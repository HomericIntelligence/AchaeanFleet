# Changelog

All notable changes to AchaeanFleet are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
No version tags exist yet; sections are anchored to commit SHAs and dates.

---

## [2026-04-05] — `20b70bc`

### Added

- GitHub CLI (`gh`) pre-installed in the base node image for CI/CD workflows

---

## [2026-04-03] — `309f75e`

### Added

- `CONTRIBUTING.md` with Dockerfile conventions, PR process, and branch strategy
- `SECURITY.md` with responsible disclosure process
- `CODE_OF_CONDUCT.md` (Contributor Covenant)
- `LICENSE` (MIT)

---

## [2026-03-31] — `a04f395`, `8b5212b`

### Fixed

- CI: use `docker` driver for buildx so daemon images are shared across build steps
- CI: load base images from build artifacts before vessel builds so `FROM` references resolve

---

## [2026-03-28] — `23bc589`

### Changed

- **Breaking:** Migrated mesh namespace from `aimaestro-mesh` → `homeric-mesh` (ADR-006)
- **Breaking:** Renamed environment variable `AIM_HOST` → `AGAMEMNON_URL`
- Replaced `agent-server.js` shim with the new Agamemnon agent sidecar entrypoint

---

## [2026-03-27] — `3ff5967`

### Added

- Enabled `hephaestus@ProjectHephaestus` plugin for CI tooling integration

---

## [2026-03-23] — `1da1354`

### Changed

- CI runners switched from self-hosted to `ubuntu-latest` for improved reliability

---

## [2026-03-15] — `5794587`, `d72575c`, `d584b71`

### Added

- Podman support: auto-detect container runtime (Docker vs Podman) in scripts
- Pod YAML specs in `pods/` for rootless Podman deployments
- `push-and-notify` recipe in `justfile`

### Fixed

- `bases/Dockerfile.node`: renamed `node` user to `agent` for Podman rootless compatibility
- Simplified runtime version display in build output

---

## [2026-03-15] — `5d6377a`

### Added

- Repository scaffold: `justfile`, `pixi.toml`, `build-all.sh`, initial `README.md`

---

## [2026-03-14] — `5bbac20`

### Added

- Initial commit: base Dockerfiles (`node`, `python`, `minimal`), vessel Dockerfiles for all
  supported agent types, Docker Compose files, and Dagger CI pipeline scaffold
