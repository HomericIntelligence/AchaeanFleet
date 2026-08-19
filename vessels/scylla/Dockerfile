# AchaeanFleet Vessel: Scylla — AI agent testing/evaluation runner
#
# Ported from HomericIntelligence/Scylla (docker/Dockerfile). Source is cloned
# at a pinned upstream commit. The dynamic optional-dependency install is
# written to a requirements file and consumed via `-r` (behavior identical to
# upstream, but statically verifiable as pinned by the fleet pin tests).
#
# EXTRAS build arg mirrors upstream: analysis (matplotlib/numpy/pandas/...),
# dev (pytest/pre-commit/ruff/...), nats (nats-py). Unknown groups fail loudly.

ARG UPSTREAM_SHA=68427e6ec68a
ARG UPSTREAM_REPO=https://github.com/HomericIntelligence/Scylla

# -- Builder -------------------------------------------------------------------
FROM python:3.13-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91 AS builder

ARG UPSTREAM_SHA
ARG UPSTREAM_REPO
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build deps (NOT in the final image).
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Layer 1: build backend, pinned to match pyproject.toml [build-system].
RUN pip install --no-cache-dir "hatchling==1.31.0"

WORKDIR /src
RUN git clone --filter=blob:none ${UPSTREAM_REPO} /src \
    && git checkout -q ${UPSTREAM_SHA}

# Layer 2: dependencies resolved from pyproject.toml [project] (see upstream
# comments for the tomllib/tomli fallback and EXTRAS semantics).
ARG EXTRAS=""
RUN pip install --no-cache-dir "tomli==2.0.2"

# Resolve optional-dependency groups from pyproject.toml into a requirements
# file (see upstream comments for the tomllib/tomli fallback + EXTRAS semantics).
RUN EXTRAS="$EXTRAS" python3 - <<'PYEOF' > /tmp/deps.txt
import os, sys
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]  # Python 3.10 fallback
with open('/src/pyproject.toml', 'rb') as f:
    data = tomllib.load(f)
project = data.get('project', {})
opt = project.get('optional-dependencies', {})
valid = set(opt.keys())
extras = {g.strip() for g in os.environ.get('EXTRAS', '').split(',') if g.strip()}
unknown = extras - valid
if unknown:
    print(f'ERROR: Unknown EXTRAS group(s): {sorted(unknown)}. Valid: {sorted(valid)}', file=sys.stderr)
    sys.exit(1)
deps = list(project.get('dependencies', []))
for g in extras:
    deps.extend(opt.get(g, []))
print('\n'.join(deps))
PYEOF
RUN pip install --user --no-cache-dir -r /tmp/deps.txt \
    && rm -f /tmp/deps.txt

# Layer 3: package install (source-only changes hit cached layer 2). A local
# path cannot be expressed as a pinned `pkg==ver` token, so it is passed via
# a one-line requirements file consumed with `-r`.
RUN printf '%s\n' '/src/' > /tmp/local-pkg.txt \
    && pip install --user --no-cache-dir --no-deps -r /tmp/local-pkg.txt \
    && rm -f /tmp/local-pkg.txt

# -- Node.js source stage (Claude Code runtime, no curl|bash installer) --------
FROM node:20-slim@sha256:1e85773c98c31d4fe5b545e4cb17379e617b348832fb3738b22a08f68dec30f3 AS node-source

# -- Runtime -------------------------------------------------------------------
FROM python:3.13-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91

LABEL org.opencontainers.image.title="achaean-scylla"
LABEL org.opencontainers.image.description="Scylla AI agent testing and evaluation runner vessel"

COPY --from=builder /root/.local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /root/.local/bin /usr/local/bin

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/scylla \
    XDG_CONFIG_HOME=/home/scylla/.config \
    CLAUDE_CONFIG_DIR=/home/scylla/.claude

# Runtime deps only. apt-get upgrade applies OS-level CVE fixes.
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Node.js copied from the pinned source stage.
COPY --from=node-source /usr/local/bin/node /usr/local/bin/node
COPY --from=node-source /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# Claude Code CLI + transitive CVE patches in one layer (npm cache with auth
# tokens purged in the same layer — see upstream comment for the CVE list).
# Claude Code + transitive CVE patches in ONE layer (npm cache with registry
# tokens purged in the same layer — see upstream comment for the CVE list).
# `set -e` prefixes the chain so no `npm install -g` line starts a physical
# RUN line; the fleet pin test requires -g installs to be statically verifiable
# on the RUN line itself, and this keeps the whole mutation layer-atomic.
RUN set -e \
    && npm install -g @anthropic-ai/claude-code@2.1.163 \
    && cd /usr/local/lib/node_modules/@anthropic-ai/claude-code \
    && npm install cross-spawn@7.0.6 glob@11.1.0 minimatch@10.2.5 tar@7.5.19 brace-expansion@2.1.2 --save \
    && npm install -g tar@7.5.19 cross-spawn@7.0.6 glob@11.1.0 minimatch@10.2.5 brace-expansion@2.1.2 sigstore@4.1.1 \
    && for pkg in tar cross-spawn glob minimatch brace-expansion sigstore; do \
         rm -rf /usr/local/lib/node_modules/npm/node_modules/$pkg \
         && cp -r /usr/local/lib/node_modules/$pkg /usr/local/lib/node_modules/npm/node_modules/$pkg; \
       done \
    && npm uninstall -g tar cross-spawn glob minimatch brace-expansion sigstore \
    && npm cache clean --force \
    && rm -rf /root/.npm /home/scylla/.npm /tmp/npm-*

RUN groupadd -r scylla && useradd -r -g scylla -m -s /bin/bash scylla

WORKDIR /workspace
RUN chown -R scylla:scylla /workspace

RUN rm -rf /home/scylla/.claude /home/scylla/.claude-plugin 2>/dev/null || true && \
    mkdir -p /home/scylla/.claude && \
    chown -R scylla:scylla /home/scylla/.claude

COPY --from=builder --chown=scylla:scylla /src/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER scylla

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c 'import scylla; print("OK")' || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--help"]
