# Contributing to AchaeanFleet

Thank you for your interest in contributing to AchaeanFleet! This is the container image
library for the [HomericIntelligence](https://github.com/HomericIntelligence) distributed
agent mesh — base images, per-agent vessel Dockerfiles, Compose files, and Dagger CI pipelines.

For an overview of the full ecosystem, see the
[Odysseus](https://github.com/HomericIntelligence/Odysseus) meta-repo.

## Quick Links

- [Development Setup](#development-setup)
- [What You Can Contribute](#what-you-can-contribute)
- [Development Workflow](#development-workflow)
- [Building and Testing](#building-and-testing)
- [Pull Request Process](#pull-request-process)
- [Code Review](#code-review)

## Development Setup

### Prerequisites

- [Git](https://git-scm.com/)
- [GitHub CLI](https://cli.github.com/) (`gh`)
- [Podman](https://podman.io/) (or Docker) for building and running containers
- [Node.js](https://nodejs.org/) 20+ (for Dagger TypeScript pipelines)
- [Pixi](https://pixi.sh/) for environment management
- [Just](https://just.systems/) as the command runner

### Environment Setup

```bash
# Clone the repository
git clone https://github.com/HomericIntelligence/AchaeanFleet.git
cd AchaeanFleet

# Activate the Pixi environment
pixi shell

# Bootstrap your development environment (recommended)
just bootstrap
```

The `bootstrap` recipe sets up your environment in one command:
- Creates `compose/.env` from the template (you'll edit it to add API keys)
- Installs Dagger TypeScript dependencies
- Displays the active container runtime (Podman or Docker)
- Instructs you to run `just build-all` next

For a full list of available recipes, run:

```bash
just --list
```

### Verify Your Setup

```bash
# Verify Podman is available
podman version

# Build all base images
just build-bases

# Verify images built successfully
just verify
```

### Linting

This project uses [pre-commit](https://pre-commit.com/) for local linting.
Hooks cover Dockerfile linting (hadolint), YAML validation (yamllint),
shell script analysis (shellcheck), and standard file hygiene.

```bash
# Install hooks (run once after cloning)
just lint-install

# Run all linters manually across all files
just lint
```

Hooks run automatically on `git commit` after installation.

### Container runtime selection

The justfile auto-detects `podman` if available, otherwise falls back to `docker`.
To override explicitly, set `CONTAINER_CMD`:

```bash
# Force Podman
CONTAINER_CMD=podman just build-all

# Force Docker
CONTAINER_CMD=docker just build-all
```

On SELinux-enforcing systems (Fedora, RHEL), Podman rootless works without additional flags —
the Compose files already include `:Z` volume labels.

## What You Can Contribute

- **Vessel Dockerfiles** — New agent-specific container images
- **Base image updates** — Improvements to shared base images in `bases/`
- **Compose topologies** — Docker Compose configurations for local development and testing
- **Dagger pipelines** — CI/CD pipeline stages in `dagger/` (TypeScript)
- **Justfile recipes** — New build, test, or deployment commands
- **Documentation** — README updates, image usage guides

## Development Workflow

### 1. Find or Create an Issue

Before starting work:

- Browse [existing issues](https://github.com/HomericIntelligence/AchaeanFleet/issues)
- Comment on an issue to claim it before starting work
- Create a new issue if one doesn't exist for your contribution

### 2. Branch Naming Convention

Create a feature branch from `main`:

```bash
git checkout main
git pull origin main
git checkout -b <issue-number>-<short-description>

# Examples:
git checkout -b 10-add-nestor-vessel
git checkout -b 7-optimize-base-image-layers
```

**Branch naming rules:**

- Start with the issue number
- Use lowercase letters and hyphens
- Keep descriptions short but descriptive

### 3. Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**

| Type       | Description                |
|------------|----------------------------|
| `feat`     | New feature                |
| `fix`      | Bug fix                    |
| `docs`     | Documentation only         |
| `style`    | Formatting, no code change |
| `refactor` | Code restructuring         |
| `test`     | Adding/updating tests      |
| `chore`    | Maintenance tasks          |

**Example:**

```bash
git commit -m "feat(vessels): add ProjectNestor vessel Dockerfile

Multi-stage build based on runtime base image. Includes
health check endpoint and non-root USER directive.

Closes #10"
```

## Building and Testing

### Build

```bash
# Build all base images
just build-bases

# Build a specific vessel image
just build-vessel nestor

# Build everything
just build-all
```

### Test

```bash
# Run Dagger smoke tests
just test

# Verify image builds and labels
just verify
```

### Run Locally

```bash
# Start the Compose stack
just compose-up

# Start the full mesh network
just mesh-up

# Tear down
just compose-down
```

### Container Conventions

- **Base images**: Defined in `bases/`, shared across all vessels
- **Vessel images**: One Dockerfile per agent/service, using multi-stage builds
- **Non-root**: All production images must include a `USER` directive
- **Pinning**: Pin base image digests, not mutable tags
- **Labels**: Include standard OCI labels (maintainer, version, description)

### CI Docker Load Pattern

The CI pipeline exports base images as tarballs and loads them in vessel build jobs using:

```bash
IMAGE_ID=$(docker load -i base.tar | awk '{print $NF}')
docker tag "$IMAGE_ID" achaean-base-node:latest
```

The `IMAGE_ID` capture is required because `docker load` on compressed tarballs may change the image
ID. A bare `docker load` without re-tagging can leave the wrong image name in the daemon, causing
vessel builds to fail with "manifest not found". Do not revert to `docker load` without `docker tag`.

### Pinning and Version Updates

Every `npm install -g` and `pip install` command in a Dockerfile must specify an exact version.
This keeps builds reproducible and prevents silent breakage from upstream updates (see issue #57).

**Finding current pinned versions**

Each tool version is declared as an `ENV` variable directly above its install command:

```dockerfile
ENV CLAUDE_CODE_VERSION=2.1.101
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}
```

Search for `ENV *_VERSION` to find all pins at once:

```bash
grep -r '_VERSION=' bases/ vessels/
```

**Discovering the latest version of a package**

```bash
# npm packages
npm view @anthropic-ai/claude-code version
npm view @openai/codex version
npm view cline version
npm view codebuff version
npm view @sourcegraph/amp version
npm view yarn version

# pip packages
pip index versions aider-chat
```

**Updating a pin**

1. Edit the `ENV <TOOL>_VERSION=<new_version>` line in the relevant Dockerfile.
2. Run the regression test to confirm all pins are still exact:

```bash
python3 -m pytest tests/test_dockerfile_pins.py -v
```

3. Rebuild the affected image and verify it starts correctly:

```bash
just build-vessel <name>
just verify
```

**Automated Dependabot PRs**

Dependabot is configured in `.github/dependabot.yml` to open monthly PRs for Docker base image
and GitHub Actions version bumps. npm tool package versions require manual review because
Dependabot cannot update inline `ENV` pins in Dockerfiles — bump these by following the steps
above when a new release of a tool is available.

**Updating pinned binary checksums (ARG-based)**

Some vessel Dockerfiles install pre-built binaries (Goose, OpenCode) via GitHub releases and verify
them with SHA256 checksums to ensure reproducibility and security. When updating these tools:

1. **Compute the new SHA256** for each architecture:

```bash
# For AMD64
curl -fsSL "https://github.com/block/goose/releases/download/v1.32.0/goose-x86_64-unknown-linux-gnu.tar.gz" | sha256sum

# For ARM64
curl -fsSL "https://github.com/block/goose/releases/download/v1.32.0/goose-aarch64-unknown-linux-gnu.tar.gz" | sha256sum
```

2. **Update the ARG values** in the relevant Dockerfile:

```dockerfile
ARG GOOSE_VERSION=1.32.0
ARG GOOSE_AMD64_SHA256=<new-amd64-hash>
ARG GOOSE_ARM64_SHA256=<new-arm64-hash>
```

3. **Important**: Both `AMD64` and `ARM64` checksums must be updated together to support multi-arch builds.

4. Test the build on both architectures to verify checksums are correct.

## Pull Request Process

### Before You Start

1. Ensure an issue exists for your work
2. Create a branch from `main` using the naming convention
3. Implement your changes
4. Run `just verify` to confirm images build correctly

### Creating Your Pull Request

```bash
git push -u origin <branch-name>
gh pr create --title "[Type] Brief description" --body "Closes #<issue-number>"
```

**PR Requirements:**

- PR must be linked to a GitHub issue
- PR title should be clear and descriptive
- Images must build successfully

### Required Status Checks

To ensure quality and security standards are enforced before merging, certain CI jobs must be configured as **required status checks** in GitHub branch protection rules. This is a **manual configuration step** — it is not automated by the workflow files.

**Jobs to configure as required status checks:**

- `Lint Dockerfiles and YAML` — Enforces Dockerfile and YAML syntax rules
- `Validate Nomad Job HCL` — Validates Nomad job specification syntax
- `Smoke Test Worker Vessel` — Runs integration tests on worker containers
- `Trivy filesystem scan (deps + secrets)` — Scans dependencies and secrets for vulnerabilities

**How to configure:**

1. Go to **Settings** → **Branches** → **Branch protection rules**
2. Select or create a rule for `main`
3. Scroll to **Require status checks to pass before merging**
4. Search for and enable each required check listed above
5. Save the rule

These checks prevent merging code that fails security or quality gates and ensure all artifacts meet the project's standards.

### Never Push Directly to Main

The `main` branch is protected. All changes must go through pull requests.

## Code Review

### What Reviewers Look For

- **Image size** — Are layers minimized? Is multi-stage build used effectively?
- **Security** — Non-root USER? No embedded secrets? Base images pinned?
- **Layer caching** — Are frequently-changing layers at the bottom of the Dockerfile?
- **Labels** — Are OCI labels present and accurate?
- **Compose correctness** — Do services start and connect properly?

### Responding to Review Comments

- Keep responses short (1 line preferred)
- Start with "Fixed -" to indicate resolution

## Markdown Standards

All documentation files must follow these standards:

- Code blocks must have a language tag (`dockerfile`, `bash`, `yaml`, `text`, etc.)
- Code blocks must be surrounded by blank lines
- Lists must be surrounded by blank lines
- Headings must be surrounded by blank lines

## Reporting Issues

### Bug Reports

Include: clear title, steps to reproduce, expected vs actual behavior, Podman/Docker version.

### Security Issues

**Do not open public issues for security vulnerabilities.**
See [SECURITY.md](SECURITY.md) for the responsible disclosure process.

## Code of Conduct

Please review our [Code of Conduct](CODE_OF_CONDUCT.md) before contributing.

---

Thank you for contributing to AchaeanFleet!
