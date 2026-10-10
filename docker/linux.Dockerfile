# syntax=docker/dockerfile:1.7
# Debian/glibc build. The workflow uses native amd64 and arm64 runners.
ARG DEBIAN_IMAGE=debian:bookworm-slim
FROM ${DEBIAN_IMAGE} AS builder
ARG TDLIB_COMMIT
ARG TDLIB_VERSION
ARG BUILD_FINGERPRINT
ARG SOURCE_DATE_EPOCH
ARG BUILD_JOBS=2
ARG TARGETARCH
ARG CACHE_BUST=stable
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then set -- -o Acquire::https::CaInfo=/run/secrets/proxy_ca; fi \
    && apt-get "$@" update && apt-get "$@" install -y --no-install-recommends \
        ca-certificates cmake g++ gcc git gperf ninja-build python3 \
        libssl-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*
RUN --mount=type=cache,id=tdlib-debian-${TARGETARCH}-${TDLIB_COMMIT}-${BUILD_FINGERPRINT}-${CACHE_BUST},target=/build \
    --mount=type=bind,source=upstream,target=/upstream,rw \
    --mount=type=bind,source=scripts,target=/scripts \
    --mount=type=bind,source=LICENSE,target=/distribution-license \
    --mount=type=bind,source=THIRD_PARTY_NOTICES.md,target=/distribution-notices \
    bash /scripts/build-linux.sh /upstream /build /opt/tdlib

FROM ${DEBIAN_IMAGE} AS runtime-base
ARG TDLIB_COMMIT
ARG TDLIB_VERSION
ARG BUILD_FINGERPRINT
LABEL org.opencontainers.image.title="TDLib for Linux (Debian)" \
      org.opencontainers.image.description="Official TDLib JSON library, compiled and smoke-tested for Linux/glibc" \
      org.opencontainers.image.source="https://github.com/vigarepo2/TDLib" \
      org.opencontainers.image.url="https://hub.docker.com/r/vs69/tdlib" \
      org.opencontainers.image.documentation="https://github.com/vigarepo2/TDLib#readme" \
      org.opencontainers.image.licenses="BSL-1.0" \
      org.opencontainers.image.version="${TDLIB_VERSION}" \
      org.opencontainers.image.revision="${TDLIB_COMMIT}" \
      io.github.vigarepo2.tdlib.build-fingerprint="${BUILD_FINGERPRINT}" \
      io.github.vigarepo2.tdlib.libc="glibc"
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then set -- -o Acquire::https::CaInfo=/run/secrets/proxy_ca; fi \
    && apt-get "$@" update && apt-get "$@" install -y --no-install-recommends \
        ca-certificates libssl3 libstdc++6 zlib1g \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 tdlib \
    && useradd --uid 10001 --gid tdlib --create-home tdlib \
    && mkdir -p /data && chown tdlib:tdlib /data
ENV TDLIB_LIBRARY_PATH=/usr/local/lib/libtdjson.so
WORKDIR /data

FROM runtime-base AS devel
USER root
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then set -- -o Acquire::https::CaInfo=/run/secrets/proxy_ca; fi \
    && apt-get "$@" update && apt-get "$@" install -y --no-install-recommends \
        cmake g++ gcc make ninja-build pkg-config libssl-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /opt/tdlib/ /usr/local/
RUN --mount=type=bind,source=scripts,target=/scripts <<'SH'
set -eu
ldconfig
tdlib-info
mkdir -p /tmp/tdlib-consumer
cat > /tmp/tdlib-consumer/CMakeLists.txt <<'CMAKE'
cmake_minimum_required(VERSION 3.16)
project(tdlib_consumer LANGUAGES C CXX)
find_package(Td REQUIRED CONFIG)
foreach(kind IN ITEMS TdJson TdJsonStatic)
  add_executable(${kind} /scripts/tdlib-info.c)
  target_link_libraries(${kind} PRIVATE Td::${kind})
  set_target_properties(${kind} PROPERTIES LINKER_LANGUAGE CXX)
endforeach()
CMAKE
cmake -S /tmp/tdlib-consumer -B /tmp/tdlib-consumer/build
cmake --build /tmp/tdlib-consumer/build
/tmp/tdlib-consumer/build/TdJson
/tmp/tdlib-consumer/build/TdJsonStatic
rm -rf /tmp/tdlib-consumer
SH
USER tdlib
CMD ["tdlib-info"]

# Keep runtime last: docker build without --target produces the small variant.
FROM runtime-base AS runtime
COPY --from=builder /opt/tdlib-runtime/ /usr/local/
RUN ldconfig && tdlib-info
USER tdlib
CMD ["tdlib-info"]
