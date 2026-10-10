# syntax=docker/dockerfile:1.7
# Alpine/musl build. GCC/libstdc++ are used consistently in build and runtime.
ARG ALPINE_IMAGE=alpine:3.23
FROM ${ALPINE_IMAGE} AS builder
ARG TDLIB_COMMIT
ARG TDLIB_VERSION
ARG BUILD_FINGERPRINT
ARG SOURCE_DATE_EPOCH
ARG BUILD_JOBS=2
ARG TARGETARCH
ARG CACHE_BUST=stable
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi \
    && apk add --no-cache bash ca-certificates cmake g++ gcc git gperf \
        linux-headers ninja openssl-dev python3 zlib-dev
RUN --mount=type=cache,id=tdlib-alpine-${TARGETARCH}-${TDLIB_COMMIT}-${BUILD_FINGERPRINT}-${CACHE_BUST},target=/build \
    --mount=type=bind,source=upstream,target=/upstream,rw \
    --mount=type=bind,source=scripts,target=/scripts \
    --mount=type=bind,source=LICENSE,target=/distribution-license \
    --mount=type=bind,source=THIRD_PARTY_NOTICES.md,target=/distribution-notices \
    bash /scripts/build-linux.sh /upstream /build /opt/tdlib

FROM ${ALPINE_IMAGE} AS runtime-base
ARG TDLIB_COMMIT
ARG TDLIB_VERSION
ARG BUILD_FINGERPRINT
LABEL org.opencontainers.image.title="TDLib for Linux (Alpine)" \
      org.opencontainers.image.description="Official TDLib JSON library, compiled and smoke-tested for Linux/musl" \
      org.opencontainers.image.source="https://github.com/vigarepo2/TDLib" \
      org.opencontainers.image.url="https://hub.docker.com/r/vs69/tdlib" \
      org.opencontainers.image.documentation="https://github.com/vigarepo2/TDLib#readme" \
      org.opencontainers.image.licenses="BSL-1.0" \
      org.opencontainers.image.version="${TDLIB_VERSION}" \
      org.opencontainers.image.revision="${TDLIB_COMMIT}" \
      io.github.vigarepo2.tdlib.build-fingerprint="${BUILD_FINGERPRINT}" \
      io.github.vigarepo2.tdlib.libc="musl"
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi \
    && apk add --no-cache ca-certificates libssl3 libcrypto3 libstdc++ libgcc zlib \
    && addgroup -g 10001 tdlib \
    && adduser -D -u 10001 -G tdlib tdlib \
    && mkdir -p /data && chown tdlib:tdlib /data
ENV TDLIB_LIBRARY_PATH=/usr/local/lib/libtdjson.so
WORKDIR /data

FROM runtime-base AS devel
USER root
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi \
    && apk add --no-cache cmake g++ gcc linux-headers make ninja pkgconf openssl-dev zlib-dev
COPY --from=builder /opt/tdlib/ /usr/local/
RUN --mount=type=bind,source=scripts,target=/scripts <<'SH'
set -eu
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

FROM runtime-base AS runtime
COPY --from=builder /opt/tdlib-runtime/ /usr/local/
RUN tdlib-info
USER tdlib
CMD ["tdlib-info"]
