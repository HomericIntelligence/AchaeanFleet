FROM ubuntu:24.04 AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake ninja-build g++ git ca-certificates libssl-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY vessels/hello-world/CMakeLists.txt vessels/hello-world/main.cpp ./
ARG NLOHMANN_JSON_VERSION=3.11.3
RUN cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DNLOHMANN_JSON_VERSION="v${NLOHMANN_JSON_VERSION}" \
    && cmake --build build

FROM ubuntu:24.04
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /src/build/hello_myrmidon /usr/local/bin/
ENV NATS_URL=nats://localhost:4222

ENTRYPOINT ["hello_myrmidon"]
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD pgrep -f hello_myrmidon > /dev/null || exit 1
