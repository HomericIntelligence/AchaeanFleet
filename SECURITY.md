# Security Policy

## Supported Images

AchaeanFleet builds container images, not versioned software releases. The following image series receive security patches:

| Image Series                   | Supported |
|--------------------------------|-----------|
| `achaean-*:latest`             | Yes       |
| `achaean-*:<sha256-digest>`    | Yes (pinned digest builds) |
| `achaean-*:<old-tag>`          | No — rebuild from `latest` |

**Policy:** Only `latest` and pinned SHA256 digest builds are supported. There are no versioned release branches; rebuild from the current `main` to get security fixes.

## Reporting Security Vulnerabilities

**Do not open public issues for security vulnerabilities.**

We take security seriously. If you discover a security vulnerability, please report it responsibly.

## How to Report

### GitHub Security Advisories (Preferred)

Use GitHub's private vulnerability reporting:

**[Report a vulnerability](https://github.com/mvillmow/AchaeanFleet/security/advisories/new)**

This is the preferred channel — it keeps the report private, lets us draft a coordinated advisory, and integrates with GitHub's Security tab automatically.

### Email (Fallback)

If you cannot use GitHub Security Advisories, send an email to: **<4211002+mvillmow@users.noreply.github.com>**

### What to Include

Please include as much of the following information as possible:

- **Description** - Clear description of the vulnerability
- **Impact** - Potential impact and severity assessment
- **Steps to reproduce** - Detailed steps to reproduce the issue
- **Affected files** - Which Dockerfiles, Compose files, or scripts are affected
- **Suggested fix** - If you have a suggested fix or mitigation

### Example Report

```text
Subject: [SECURITY] Base image runs as root without USER directive

Description:
The base Dockerfile at bases/runtime.Dockerfile does not include a
USER directive, causing all derived containers to run as root by default.

Impact:
A container escape vulnerability in any derived service would grant
root access to the host.

Steps to Reproduce:
1. Build the runtime base image: just build-bases
2. Inspect: podman inspect <image> | jq '.[0].Config.User'
3. Observe User is empty (root)

Affected Files:
bases/runtime.Dockerfile

Suggested Fix:
Add a non-root USER directive after the final COPY stage.
```

## Response Timeline

We aim to respond to security reports within the following timeframes:

| Stage                    | Timeframe              |
|--------------------------|------------------------|
| Initial acknowledgment   | 48 hours               |
| Preliminary assessment   | 1 week                 |
| Fix development          | Varies by severity     |
| Public disclosure        | After fix is released  |

## Severity Assessment

We use the following severity levels:

| Severity     | Description                          | Response           |
|--------------|--------------------------------------|--------------------|
| **Critical** | Remote code execution, data breach   | Immediate priority |
| **High**     | Privilege escalation, data exposure  | High priority      |
| **Medium**   | Limited impact vulnerabilities       | Standard priority  |
| **Low**      | Minor issues, hardening              | Scheduled fix      |

## Responsible Disclosure

We follow responsible disclosure practices:

1. **Report privately** - Do not disclose publicly until a fix is available
2. **Allow reasonable time** - Give us time to investigate and develop a fix
3. **Coordinate disclosure** - We will work with you on disclosure timing
4. **Credit** - We will credit you in the security advisory (if desired)

## What We Will Do

When you report a vulnerability:

1. Acknowledge receipt within 48 hours
2. Investigate and validate the report
3. Develop and test a fix
4. Release the fix
5. Publish a security advisory

## Scope

### In Scope

**Credential exposure**
- API keys, tokens, or secrets embedded in Dockerfiles, Compose files, or CI config (`ENV`, `ARG`, `--build-arg`, `.env` files checked in)
- Home directory mounts (`- /home/...:/home/...`) that expose host credentials or SSH keys to containers

**Privilege escalation**
- Missing `USER` directive — containers running as root by default
- `NOPASSWD` sudo grants inside images
- Dangerous Linux capability grants (`--cap-add`, `SYS_ADMIN`, etc.)
- Writable volume mounts into sensitive host paths

**Config injection**
- Insecure Docker Compose overrides that allow environment variable injection
- Build arguments that propagate secrets into image layers
- Writable socket or socket-proxy mounts without authentication

**Supply chain risks**
- Base image CVEs: OS package vulnerabilities introduced via `apt`/`apk` in `bases/` or `vessels/`
- npm transitive dependency CVEs in Node-based vessels
- `curl | bash` or `wget | sh` install patterns without checksum verification
- Mutable image tags (`:latest` used as `FROM` without pinned digest in production)

**Other**
- Dockerfiles (base images and vessel images)
- Docker Compose files (`compose/`)
- Dagger CI pipeline scripts (`dagger/`)
- Nomad job specs (`nomad/`)
- GitHub Actions workflows (`.github/`)

### Out of Scope

- Application code in service repos (report to that repo directly)
- Third-party base images (report upstream to the image maintainer)
- Social engineering attacks
- Physical security

## Automated Detection

AchaeanFleet CI runs [Trivy](https://github.com/aquasecurity/trivy-action) on all images with `severity: HIGH,CRITICAL`. CVEs already detected by Trivy in CI are tracked as issues; you do not need to report these separately unless you have additional exploitation context or a bypass.

## Security Best Practices

When contributing to AchaeanFleet:

- Never embed secrets, API keys, or credentials in Dockerfiles or build args
- Use multi-stage builds to avoid leaking build tools into production images
- Pin base image digests rather than mutable tags
- Include a non-root `USER` directive in all production images
- Scan images for known CVEs before pushing

## Contact

For security-related questions that are not vulnerability reports:

- Open a GitHub Discussion with the "security" tag
- Email: <4211002+mvillmow@users.noreply.github.com>

---

Thank you for helping keep HomericIntelligence secure!
