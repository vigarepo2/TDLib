# syntax=docker/dockerfile:1
FROM scratch
ARG TDLIB_COMMIT
ARG TDLIB_VERSION
ARG BUILD_FINGERPRINT
LABEL org.opencontainers.image.title="TDLib platform packages" \
      org.opencontainers.image.description="Archive carrier: Windows, Apple, browser and Android packages. Not a runnable server." \
      org.opencontainers.image.url="https://hub.docker.com/r/vs69/tdlib" \
      org.opencontainers.image.source="https://github.com/vigarepo2/TDLib" \
      org.opencontainers.image.version="${TDLIB_VERSION}" \
      org.opencontainers.image.revision="${TDLIB_COMMIT}" \
      org.opencontainers.image.licenses="BSL-1.0" \
      io.vs69.tdlib.build-fingerprint="${BUILD_FINGERPRINT}"
COPY packages-payload/ /opt/tdlib/packages/
# A dummy command allows `docker create`, followed by `docker cp`. Do not run it.
CMD ["/package-carrier"]
