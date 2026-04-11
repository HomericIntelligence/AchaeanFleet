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

# List available recipes
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
