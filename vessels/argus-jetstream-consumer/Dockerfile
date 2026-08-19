# AchaeanFleet Vessel: Argus JetStream Consumer — NATS JetStream sink
#
# Ported from HomericIntelligence/Argus (jetstream-consumer/Dockerfile).
# Source is cloned at a pinned upstream commit; runtime deps are baked in at
# build time (deterministic, air-gap compatible — Argus #171).

ARG UPSTREAM_SHA=59727bb5c86a
ARG UPSTREAM_REPO=https://github.com/HomericIntelligence/Argus

FROM python:3.13-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91 AS builder
ARG UPSTREAM_SHA
ARG UPSTREAM_REPO
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone --filter=blob:none ${UPSTREAM_REPO} /src \
    && git checkout -q ${UPSTREAM_SHA}

# -- Runtime -------------------------------------------------------------------
FROM python:3.13-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91

LABEL org.opencontainers.image.title="achaean-argus-jetstream-consumer"
LABEL org.opencontainers.image.description="Argus JetStream consumer — fleet NATS sink vessel"

WORKDIR /app

# Install pinned runtime deps at build time.
COPY --from=builder /src/jetstream-consumer/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

RUN groupadd -g 1000 consumer \
    && useradd -u 1000 -g consumer --no-create-home --shell /sbin/nologin consumer

COPY --from=builder --chown=consumer:consumer /src/jetstream-consumer/consumer.py /app/consumer.py

USER consumer

EXPOSE 9101

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:9101/health', timeout=4)"

ENTRYPOINT ["python3", "/app/consumer.py"]
