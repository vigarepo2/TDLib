# syntax=docker/dockerfile:1
FROM scratch
ARG PACKAGE=packages
ARG TDLIB_COMMIT
ARG TDLIB_VERSION
ARG BUILD_FINGERPRINT
LABEL org.opencontainers.image.title="TDLib ${PACKAGE}" \
      org.opencontainers.image.description="Prebuilt TDLib files with source manifests and checksums. Extract with docker cp." \
      org.opencontainers.image.url="https://hub.docker.com/r/vs69/tdlib" \
      org.opencontainers.image.source="https://github.com/vigarepo2/TDLib" \
      org.opencontainers.image.version="${TDLIB_VERSION}" \
      org.opencontainers.image.revision="${TDLIB_COMMIT}" \
      org.opencontainers.image.licenses="BSL-1.0" \
      io.github.vigarepo2.tdlib.build-fingerprint="${BUILD_FINGERPRINT}"
COPY ${PACKAGE}-payload/ /opt/tdlib/${PACKAGE}/
# A dummy command allows `docker create`, followed by `docker cp`. Do not run it.
CMD ["/package-carrier"]
