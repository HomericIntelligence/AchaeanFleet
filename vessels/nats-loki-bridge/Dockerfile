# AchaeanFleet Vessel: NATS→Loki bridge — structured-log shipping service
#
# Ported from HomericIntelligence/Odysseus (e2e/nats-loki-bridge/Dockerfile).
# Source is cloned at a pinned upstream commit. nats-py is pinned to the same
# version Hermes ships in requirements.lock.txt (2.15.0).
#
# The HEALTHCHECK verifies NATS reachability from inside the container — the
# bridge is a JetStream consumer, so NATS connectivity is its liveness signal.

ARG UPSTREAM_SHA=a05d2b49899a
ARG UPSTREAM_REPO=https://github.com/HomericIntelligence/Odysseus

FROM python:3.11-slim@sha256:9c900dea9e8fb7e16277c179b555cc72d29a352dbc33cff48ad5a0412fd5bfc7 AS builder
ARG UPSTREAM_SHA
ARG UPSTREAM_REPO
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone -q ${UPSTREAM_REPO} /src \
    && git -C /src checkout -q ${UPSTREAM_SHA}

# -- Runtime -------------------------------------------------------------------
FROM python:3.11-slim@sha256:9c900dea9e8fb7e16277c179b555cc72d29a352dbc33cff48ad5a0412fd5bfc7

LABEL org.opencontainers.image.title="achaean-nats-loki-bridge"
LABEL org.opencontainers.image.description="NATS-to-Loki log bridge — fleet observability vessel"

WORKDIR /app

# Apply current Debian security updates to the pinned slim runtime layer.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "nats-py==2.15.0"
RUN useradd -r -s /usr/sbin/nologin bridge

COPY --from=builder --chown=bridge:bridge /src/e2e/nats-loki-bridge/bridge.py /app/bridge.py

USER bridge

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import asyncio, nats, os; asyncio.run(nats.connect(os.environ.get('NATS_URL', 'nats://localhost:4222'), connect_timeout=2))"]

ENTRYPOINT ["python", "bridge.py"]
