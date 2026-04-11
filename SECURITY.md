# Security Policy

## Reporting Security Vulnerabilities

**Do not open public issues for security vulnerabilities.**

We take security seriously. If you discover a security vulnerability, please report it responsibly.

## How to Report

### Email (Preferred)

Send an email to: **<4211002+mvillmow@users.noreply.github.com>**

Or use the GitHub private vulnerability reporting feature if available.

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

- Dockerfiles (base images and vessel images)
- Docker Compose files
- Dagger CI pipeline scripts (`dagger/`)
- Justfile recipes
- Nomad job specs

### Out of Scope

- Application code in service repos (report to that repo directly)
- Third-party base images (report upstream to the image maintainer)
- Social engineering attacks
- Physical security

## TLS Architecture

All inter-service communication within the homeric-mesh is encrypted.
See [`tls/README.md`](tls/README.md) for the full architecture.

**Quick summary:**

- A Caddy reverse proxy (`compose/docker-compose.caddy.yml`) terminates TLS on port `8443`
- Agent containers connect to `https://caddy:8443` (not directly to Agamemnon on `http://8080`)
- A local CA certificate is mounted at `/certs/ca.crt` in each container for validation
- NATS (when integrated) uses `tls://nats:4222` — see `tls/nats/nats-tls.conf`

**To set up TLS before starting the mesh:**
```bash
bash tls/generate-certs.sh
```

**Private keys are git-ignored** — `tls/certs/` is excluded from version control.

See [ADR-007](docs/adr/007-tls-mesh-communications.md) for the architectural decision record.

## Security Best Practices

When contributing to AchaeanFleet:

- Never embed secrets, API keys, or credentials in Dockerfiles or build args
- Use multi-stage builds to avoid leaking build tools into production images
- Pin base image digests rather than mutable tags
- Include a non-root `USER` directive in all production images
- Scan images for known CVEs before pushing
- Never commit TLS private keys — `tls/certs/` is in `.gitignore`
- Run `bash tls/generate-certs.sh` locally; distribute certs to hosts out-of-band

## Contact

For security-related questions that are not vulnerability reports:

- Open a GitHub Discussion with the "security" tag
- Email: <4211002+mvillmow@users.noreply.github.com>

---

Thank you for helping keep HomericIntelligence secure!
