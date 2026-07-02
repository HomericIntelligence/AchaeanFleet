# AchaeanFleet Vessel: HMAS Mesh Worker
#
# Extends achaean-claude with the Hephaestus mesh worker library and the
# Telemachy CLI so a container can serve one role-addressed (domain, role)
# NATS work queue per Odysseus ADR-013. LLM work (planning, implementing,
# research/interviewing) runs inside this vessel via the bundled Claude Code
# CLI; the mesh worker claim loop is `hephaestus-mesh-worker`.
#
# Build (the base chain must exist first):
#   just build-vessel mesh
#
# HEPHAESTUS_REF / TELEMACHY_REF pin the installed library revisions; pass a
# tag or commit SHA for reproducible builds (default: main).

ARG BASE_IMAGE=achaean-claude:latest
# hadolint ignore=DL3006
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-mesh"
LABEL org.opencontainers.image.description="HMAS mesh worker vessel — hephaestus[mesh] + telemachy on achaean-claude"

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.revision=${VCS_REF}
LABEL org.opencontainers.image.version=${VERSION}
LABEL git-sha=${GIT_SHA}

USER root

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# python3 comes from the node base; pip/venv are needed for the worker venv.
RUN apt-get update \
    && apt-get install -y python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Install the mesh worker library + Telemachy CLI into an isolated venv.
# Pin HEPHAESTUS_REF/TELEMACHY_REF to a tag or SHA for reproducible builds.
ARG HEPHAESTUS_REF=main
ARG TELEMACHY_REF=main
RUN python3 -m venv /opt/mesh \
    && /opt/mesh/bin/pip install --no-cache-dir \
        "HomericIntelligence-Hephaestus[mesh] @ git+https://github.com/HomericIntelligence/ProjectHephaestus.git@${HEPHAESTUS_REF}" \
        "telemachy @ git+https://github.com/HomericIntelligence/ProjectTelemachy.git@${TELEMACHY_REF}"

ENV PATH="/opt/mesh/bin:${PATH}"
ENV TELEMACHY_BIN=/opt/mesh/bin/telemachy

# Verify installation
RUN hephaestus-mesh-worker --help > /dev/null
RUN telemachy --help > /dev/null
RUN claude --version
RUN gh --version

USER agent

# Queue selection — override per compose service (ADR-013 §1).
ENV MESH_DOMAIN=pipeline
ENV MESH_ROLE=task-agent

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD pgrep -f hephaestus-mesh-worker > /dev/null || exit 1

CMD ["hephaestus-mesh-worker"]
