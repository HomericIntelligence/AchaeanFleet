FROM ubuntu:24.04 AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake ninja-build g++ git ca-certificates libssl-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY CMakeLists.txt main.cpp ./
ARG NLOHMANN_JSON_VERSION=3.11.3
RUN cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DNLOHMANN_JSON_VERSION="v${NLOHMANN_JSON_VERSION}" \
    && cmake --build build

FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /src/build/hello_myrmidon /usr/local/bin/
ENV NATS_URL=nats://localhost:4222
CMD ["hello_myrmidon"]
