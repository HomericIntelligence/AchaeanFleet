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

## Container Runtime Hardening

All compose services apply the following runtime security options.

### `no-new-privileges:true`

```yaml
security_opt:
  - no-new-privileges:true
```

Prevents any process inside the container from gaining additional privileges via `setuid`/`setgid` binaries. This means even if a container binary has the setuid bit set, the kernel will not allow privilege escalation through it. This is particularly important given that base images grant the `agent` user passwordless `sudo` — `no-new-privileges` ensures that path cannot be exploited from within the container.

### `cap_drop: ALL`

```yaml
cap_drop:
  - ALL
```

Drops the entire set of Linux capabilities that Docker grants by default, including:

| Capability | Why dropped |
|-----------|-------------|
| `NET_RAW` | Agent containers don't send raw network packets |
| `SYS_CHOWN` | No ownership changes needed at runtime |
| `CHOWN` | Same as above |
| `SETUID` / `SETGID` | No privilege transitions needed |
| `KILL` | Agents don't need to signal arbitrary processes |
| `NET_BIND_SERVICE` | Ports are above 1024; not needed |
| `AUDIT_WRITE` | No kernel audit logging needed |
| Others | Not required for AI tool execution |

No `cap_add` entries are included — none of the current vessel types (claude, codex, aider, goose, cline, opencode, codebuff, ampcode, worker) require any capabilities beyond an unprivileged userspace process.

### Seccomp

A custom seccomp profile is not currently shipped. Docker's default seccomp profile remains active (it blocks ~44 dangerous syscalls). A vessel-specific profile is deferred to a follow-on issue.

### Runtime Validation

To confirm reduced privileges on a running container:

```bash
# Verify no-new-privileges and cap_drop are applied
docker inspect hi-aindrea | jq '.[0].HostConfig | {SecurityOpt, CapDrop, CapAdd}'

# Expected output:
# {
#   "SecurityOpt": ["no-new-privileges:true"],
#   "CapDrop": ["ALL"],
#   "CapAdd": null
# }
```

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
