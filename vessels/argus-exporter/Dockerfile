# AchaeanFleet Vessel: Argus Exporter — NATS/metrics exporter (stdlib only)
#
# Ported from HomericIntelligence/Argus (exporter/Dockerfile). Source is cloned
# at a pinned upstream commit. This is the canonical argus-exporter image —
# the e2e copy in Odysseus (e2e/Dockerfile.argus-exporter) is de-duplicated in
# favor of this vessel.

ARG UPSTREAM_SHA=59727bb5c86a
ARG UPSTREAM_REPO=https://github.com/HomericIntelligence/Argus

FROM python:3.14-slim@sha256:ce40764625a4ff50df3548277632e7f96c4e77fe75fa848aae9885476e7df5a4 AS builder
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
FROM python:3.14-slim@sha256:ce40764625a4ff50df3548277632e7f96c4e77fe75fa848aae9885476e7df5a4

LABEL org.opencontainers.image.title="achaean-argus-exporter"
LABEL org.opencontainers.image.description="Argus exporter — fleet NATS/metrics exporter vessel"

# No extra packages — exporter uses stdlib only.
WORKDIR /app

RUN groupadd -g 1000 exporter \
    && useradd -u 1000 -g exporter --no-create-home --shell /sbin/nologin exporter

COPY --from=builder --chown=exporter:exporter /src/exporter/exporter.py /app/exporter.py

USER exporter

EXPOSE 9100

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:9100/health', timeout=4)"

ENTRYPOINT ["python3", "/app/exporter.py"]
