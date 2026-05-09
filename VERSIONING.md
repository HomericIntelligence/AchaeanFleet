# Versioning Strategy

> **File guide** — three versioning-related files exist in this repo; each serves a distinct purpose:
>
> | File | Purpose |
> |------|---------|
> | `VERSIONING.md` | This file — describes the image tagging strategy (CalVer + git SHA). |
> | `VERSIONS.md` | Tracks pinned tool versions inside vessel Dockerfiles. |
> | `VERSION` | Records the last CalVer release date; not consumed by CI or justfile. |

AchaeanFleet uses a three-tier image tagging strategy to support both mutable continuous deployments
and immutable release pinning.

## Tag Types

### Automatic Tags (Every Push to main)

Every push to the `main` branch produces three tags per image:

- **`:latest`** — Mutable tag pointing to the most recent main build. Use for development and fast-moving deployments.
- **`:git-<7sha>`** — Immutable tag with the 7-character git commit SHA. Recommended for pinning to
  a specific commit.
- **`:YYYY-MM-DD-<7sha>`** — Immutable date-keyed tag with SHA suffix. Useful for audit trails and
  collision-safe rollback.

Example (commit abc1234 pushed 2026-04-23):

```
ghcr.io/homericintelligence/achaean-claude:latest
ghcr.io/homericintelligence/achaean-claude:git-abc1234
ghcr.io/homericintelligence/achaean-claude:2026-04-23-abc1234
```

### Release Tags (Version Tag Pushes)

When you push a git tag matching `vMAJOR.MINOR.PATCH` (e.g., `v1.2.3`), the CI workflow additionally
produces:

- **`:vMAJOR.MINOR.PATCH`** — Full semver tag, e.g., `:v1.2.3`
- **`:MAJOR.MINOR`** — Minor-level alias for automatic minor-version upgrades, e.g., `:1.2`

Example (pushing tag `v1.2.3`):

```
ghcr.io/homericintelligence/achaean-claude:v1.2.3
ghcr.io/homericintelligence/achaean-claude:1.2
ghcr.io/homericintelligence/achaean-claude:git-abc1234  # also created
ghcr.io/homericintelligence/achaean-claude:2026-04-23-abc1234  # also created
ghcr.io/homericintelligence/achaean-claude:latest  # updated
```

## Creating a Release

1. **Bump the version** in your local repository by deciding on the next semantic version
   (e.g., `1.2.0` → `1.2.1`).
1. **Create and push the release tag**:

   ```bash
   git tag v1.2.1
   git push origin v1.2.1
   ```

1. **Validate the release**: The `release.yml` workflow will trigger automatically, validate the tag
   format, and push images with all appropriate tags to GHCR.

Tags must match the pattern `v[0-9]+.[0-9]+.[0-9]+` (e.g., `v1.0.0`, `v1.2.3`). The workflow will reject malformed tags.

## Pinning Deployments

Use the `IMAGE_TAG` variables in `compose/.env` to pin specific image versions:

```bash
# Pin to latest (mutable)
CLAUDE_IMAGE=achaean-claude:latest

# Pin to a specific commit (immutable, safest for rollback)
CLAUDE_IMAGE=achaean-claude:git-abc1234

# Pin to a specific date (immutable, good for audit trails)
CLAUDE_IMAGE=achaean-claude:2026-04-10

# Pin to a release version (immutable, for production)
CLAUDE_IMAGE=achaean-claude:v1.2.3

# Use minor-version tracking (semver ^1.2.0)
CLAUDE_IMAGE=achaean-claude:1.2
```

Always specify the full registry path for remote deployments:

```bash
CLAUDE_IMAGE=ghcr.io/homericintelligence/achaean-claude:git-abc1234
```

## CI Workflows

- **`ci.yml`** (on push to main): Builds and validates all images; pushes `:latest`, `:git-<sha>`,
  and `:YYYY-MM-DD-<sha>` tags.
- **`release.yml`** (on version tag push): Validates semver format; builds and pushes
  `:vMAJOR.MINOR.PATCH` and `:MAJOR.MINOR` tags.

Both workflows inherit all commit-based tags from the triggering commit.
