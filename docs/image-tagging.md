# AchaeanFleet Image Tagging Strategy

Every push to `main` produces **three tags per image**, built once and published atomically.

## Tag formats

| Tag | Mutability | Use case |
|-----|-----------|----------|
| `:latest` | Mutable | "Give me the current build" — convenience alias, not for reproducible deploys |
| `:git-<7sha>` | Immutable | Precise rollback to a known commit — preferred for production |
| `:YYYY-MM-DD-<7sha>` | Immutable | Date-keyed, collision-safe — useful for audit trails and staging |

### Why not bare `:YYYY-MM-DD`?

A bare date tag is overwritten on every push to `main` that occurs on the same calendar day. The SHA
suffix (`-<7sha>`) disambiguates multiple same-day pushes and makes the tag immutable once created.

## Examples

For a push with commit `abc1234…` on 2026-04-23, each image receives:

```
ghcr.io/homericintelligence/achaean-claude:latest
ghcr.io/homericintelligence/achaean-claude:git-abc1234
ghcr.io/homericintelligence/achaean-claude:2026-04-23-abc1234
```

Two pushes on the same day produce distinct date tags:

```
2026-04-23-abc1234   ← first push
2026-04-23-def5678   ← second push (different SHA)
```

## Rollback procedure

**By commit:**

```bash
# Edit compose/.env or docker-compose override:
CLAUDE_IMAGE=ghcr.io/homericintelligence/achaean-claude:git-abc1234
docker compose up -d
```

**By date:**

```bash
CLAUDE_IMAGE=ghcr.io/homericintelligence/achaean-claude:2026-04-23-abc1234
docker compose up -d
```

**List available tags:**

```bash
gh api /orgs/homericintelligence/packages/container/achaean-claude/versions \
  --jq '.[].metadata.container.tags[]'
```

## CI mechanics

The `push-to-registry` job in `.github/workflows/ci.yml`:

1. Runs a **Compute build metadata** step that safely captures `GITHUB_SHA` via an `env:` block
   (avoiding shell injection) and writes `short_sha` and `date_tag` to `$GITHUB_OUTPUT`.
1. Passes `SHORT_SHA` and `DATE_TAG` as environment variables to the Dagger pipeline.
1. The Dagger pipeline (`dagger/pipeline.ts`) reads those env vars and publishes all three tags in a
   loop — images are built **once** and pushed with multiple tags.

Local builds (no env vars set) fall back to `:latest` and `:local-<local>` tags so development workflows are unaffected.

## Tag Retention and Cleanup

### Tag mutability

- **`:latest`** — Mutable. Overwritten on every push to `main`. Do not rely on it for reproducible
  deployments.
- **`:git-<sha>` and `:YYYY-MM-DD-<sha>`** — Immutable once created. These tags accumulate
  indefinitely in GHCR, as new commits and days produce new tags.

### Cleanup policy

With three tags per push, untagged manifests and old tags can accumulate in GHCR over time. We recommend:

1. **Untagged manifests**: Delete all manifests older than 90 days. These accumulate when tags are
   pruned but the underlying layers remain.
1. **Tagged historical images**: Set a retention window (e.g., keep all tags from the last 180 days,
   prune older ones).
1. **Automation**: Enable "Delete untagged versions" in the GHCR package settings for each agent image.

### Listing and managing tags

**List all tags for an image:**

```bash
gh api /orgs/HomericIntelligence/packages/container/achaean-claude/versions \
  --jq '.[] | .metadata.container.tags[]'
```

**Find old tags (example: tags older than 90 days):**

```bash
gh api /orgs/HomericIntelligence/packages/container/achaean-claude/versions \
  --jq '.[] | select(.created_at < now - 7776000) | {id, created_at, tags: .metadata.container.tags[]}'
```

### GHCR configuration

GHCR does not have built-in automatic pruning. To reduce accumulation:

1. In the GitHub UI, navigate to **Settings → Packages and registries → Package settings** for each
   agent image.
1. Enable **"Delete untagged versions"** to remove orphaned manifests automatically.
1. Set a retention policy for tagged versions manually or via scheduled GitHub Actions, if needed.

For production deployments, pin to immutable tags (`:git-<sha>` or `:YYYY-MM-DD-<sha>`) and monitor
the package registry periodically for cleanup.
