# Local CI

Build the native CI image, then run the repository's checks:

```bash
just ci-build
just ci-all
```

The image supports Linux AMD64 and ARM64. Both retain the same Python base
digest, Pixi 0.70.2 and UV 0.12.10. Binary downloads use architecture-specific
checksums before installation. Node 22.23.2 and npm 10.9.8 come from a pinned
image; `ci/package-lock.json` locks the Markdown CLI. Hadolint is installed in
the image because its pre-commit hook uses a system executable.

The `dev` Pixi environment supplies Python tests and pre-commit on both
architectures. AMD64 retains its conda BATS package. ARM64 uses Debian BATS
because conda-forge does not publish `bats-core` for that platform.
Adding ARM64 preserves both existing AMD64 environment selections. The
regenerated lock also records empty `run_exports` metadata for ten shared
noarch packages; their URLs, hashes and dependencies are unchanged.

`ci-all` runs these existing subsets in order and stops on the first failure:

1. `lint`: the configured pre-commit hooks.
2. `markdownlint`: repository Markdown files.
3. `pixi-check`: locked environment installation.
4. `unit-tests`: Python tests and recursive BATS tests.
5. `integration-tests`: Compose validation with the required Caddy overlay.
6. `schema-validation`: existing Nomad/pod tests and Nomad job validation.
7. `security-secrets-scan`: Gitleaks with its original failure status.
8. `security-dependency-scan`: Trivy HIGH/CRITICAL findings fail the command.
9. `deps-version-sync`: existing Dockerfile pin and checksum tests.
10. `forbid-suppressions`: the three configured suppression guards.
11. `justfile-check`: Just syntax evaluation.
12. `symlink-check`: the repository's symlink checker.

The existing `just ci-<subset>` recipes select individual checks. The dependency
scanner is also available through the script entrypoint:

```bash
just --command bash scripts/run_ci_local.sh security-dependency-scan
```

`tests/test_ci_local.py` exercises dispatch and failure propagation with
controlled engine/tool fixtures. `tests/test_ci_image.py` checks source
contracts. Neither replaces building the image or running the real checks.
Hosted CI also has image publication and other required contexts; passing the
local subsets does not establish that those hosted checks have passed.
