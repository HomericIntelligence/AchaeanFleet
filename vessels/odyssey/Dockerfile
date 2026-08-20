# AchaeanFleet Vessel: Odyssey — Mojo ML training/development environment
#
# Ported from HomericIntelligence/Odyssey (Dockerfile). Source is cloned at a
# pinned upstream commit. The Mojo compiler (mojo==1.0.0b2) is resolved from
# the public Modular PyPI index via uv sync (Odysseus ADR-018); the vessel
# ships the uv-managed venv + workspace so training runs work out of the box.
#
# The upstream image builds an intermediate ubuntu:24.04 from the
# mcr.microsoft.com mirror; the vessel pins the docker.io multi-arch digest
# (same content, reproducible — see Odysseus ADR-008 podman-over-docker).

ARG UPSTREAM_SHA=124590b1e2f4
ARG UPSTREAM_REPO=https://github.com/HomericIntelligence/Odyssey

# -- uv binary source -----------------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.12.3@sha256:2d890623d310b57771ce840f0da5eed5fc6d657da05ffaa45d82797b53fa3abc AS uv

# -- Builder: system deps + dev user + locked venv ------------------------------
FROM ubuntu:24.04@sha256:c4a8d5503dfb2a3eb8ab5f807da5bc69a85730fb49b5cfca2330194ebcc41c7b AS builder

ARG UPSTREAM_SHA
ARG UPSTREAM_REPO
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    libasan8 \
    ca-certificates \
    vim \
    wget \
    uuid \
    sudo \
    gdb \
    && rm -rf /var/lib/apt/lists/*

# GitHub CLI (gh) from the official apt repo.
RUN mkdir -p -m 755 /etc/apt/keyrings \
    && out=$(mktemp) && wget -nv -O$out https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    && cat $out | tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
    && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && mkdir -p -m 755 /etc/apt/sources.list.d \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://just.systems/install.sh | bash -s -- --to /usr/local/bin --tag 1.14.0

COPY --from=uv /uv /uvx /usr/local/bin/

ARG USER_ID=1000
ARG GROUP_ID=1000
ARG USER_NAME=dev

RUN groupadd -g ${GROUP_ID} ${USER_NAME} 2>/dev/null || \
    groupmod -n ${USER_NAME} $(getent group ${GROUP_ID} | cut -d: -f1) && \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} -s /bin/bash ${USER_NAME} 2>/dev/null || \
    usermod -l ${USER_NAME} -d /home/${USER_NAME} -m $(id -nu ${USER_ID} 2>/dev/null || echo nobody) && \
    chmod 755 /home/${USER_NAME}

# Allow dev user to fix bind-mount ownership at container startup.
RUN printf 'dev ALL=(root) NOPASSWD: /bin/mkdir\ndev ALL=(root) NOPASSWD: /bin/chown\ndev ALL=(root) NOPASSWD: /bin/chmod\n' \
    > /etc/sudoers.d/dev-workspace \
    && chmod 440 /etc/sudoers.d/dev-workspace

ENV HOME=/home/${USER_NAME}
ENV PATH="$HOME/.local/bin:$HOME/.venv/bin:$PATH"

WORKDIR /src
RUN git clone -q ${UPSTREAM_REPO} /src \
    && git -C /src checkout -q ${UPSTREAM_SHA}

# Security pin for the distro-shipped system python (trivy flags setuptools
# 70.3.0 + msgpack 1.1.2 on noble) — run as root before dropping to dev.
# PEP 668 requires --break-system-packages for the distro-managed interpreter.
RUN if command -v python3 >/dev/null 2>&1; then \
        python3 -m ensurepip --upgrade --break-system-packages >/dev/null 2>&1; \
        python3 -m pip install --no-cache-dir --break-system-packages \
            setuptools==83.0.0 msgpack==1.2.1; \
    fi

RUN chown -R ${USER_ID}:${GROUP_ID} /src

# Copy entrypoint script from the clone while still root (a bare COPY would
# read the build context, where /src does not exist; /usr/local/bin is not
# writable by the dev user). Chown to dev so the bind-mount fix can rewrite it.
RUN cp /src/docker/entrypoint.sh /usr/local/bin/entrypoint.sh \
    && chown ${USER_NAME}:${USER_NAME} /usr/local/bin/entrypoint.sh \
    && chmod +x /usr/local/bin/entrypoint.sh

USER ${USER_NAME}

ENV UV_CACHE_DIR=/home/${USER_NAME}/.cache/uv
ENV UV_PROJECT_ENVIRONMENT=/home/${USER_NAME}/.venv
ENV UV_PYTHON_INSTALL_DIR=/home/${USER_NAME}/.local/share/uv/python
RUN mkdir -p $UV_CACHE_DIR $HOME/.modular

# Install project dependencies incl. the Mojo compiler. --no-install-project:
# only third-party deps + the toolchain are baked in; the workspace source is
# already present from the clone (no runtime bind-mount in the fleet vessel).
RUN uv sync --locked --no-install-project

RUN uv run pre-commit --version

# Install pre-commit hooks (the clone is already a git repo, so hook envs can
# be cloned without the upstream's throwaway-repo workaround).
RUN git config --global user.email "build@odyssey.local" && \
    git config --global user.name "build" && \
    git config --global init.defaultBranch main && \
    uv run pre-commit install --install-hooks

ENV PYTHONPATH=/src:${PYTHONPATH:-}

# -- Runtime -------------------------------------------------------------------
FROM ubuntu:24.04@sha256:c4a8d5503dfb2a3eb8ab5f807da5bc69a85730fb49b5cfca2330194ebcc41c7b

LABEL org.opencontainers.image.title="achaean-odyssey"
LABEL org.opencontainers.image.description="Odyssey Mojo ML training/development environment vessel"

ARG USER_NAME=dev

# Minimal runtime deps (git + ca-certificates for training checkpoints / git
# refs; sudo + bash for the entrypoint's ownership fix).
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    sudo \
    bash \
    && rm -rf /var/lib/apt/lists/* \
    && (groupadd -g 1000 ${USER_NAME} 2>/dev/null || \
        groupmod -n ${USER_NAME} $(getent group 1000 | cut -d: -f1)) \
    && (useradd -m -u 1000 -g 1000 -s /bin/bash ${USER_NAME} 2>/dev/null || \
        usermod -l ${USER_NAME} -d /home/${USER_NAME} -m $(id -nu 1000 2>/dev/null || echo nobody)) \
    && chmod 755 /home/${USER_NAME} \
    && printf 'dev ALL=(root) NOPASSWD: /bin/mkdir\ndev ALL=(root) NOPASSWD: /bin/chown\ndev ALL=(root) NOPASSWD: /bin/chmod\n' \
        > /etc/sudoers.d/dev-workspace \
    && chmod 440 /etc/sudoers.d/dev-workspace

COPY --from=builder /home/${USER_NAME}/.venv /home/${USER_NAME}/.venv
COPY --from=builder /src /workspace
COPY --from=builder /usr/local/bin/entrypoint.sh /usr/local/bin/entrypoint.sh

ENV ENVIRONMENT=production
ENV PATH="/home/${USER_NAME}/.venv/bin:${PATH}"
ENV PYTHONPATH=/workspace:${PYTHONPATH:-}
USER ${USER_NAME}
WORKDIR /workspace

# Dev/training vessel: default to an interactive bash; `docker run ... bash -c
# "mojo run train.mojo"` works as expected.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["bash", "-c", "kill -0 1 || exit 1"]

ENTRYPOINT ["/bin/bash"]
CMD []
