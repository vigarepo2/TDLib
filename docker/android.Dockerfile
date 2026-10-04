# Android artifact carrier. This is not a Linux TDLib runtime or SDK/toolchain.
FROM scratch
ARG TDLIB_VERSION
ARG TDLIB_COMMIT
ARG BUILD_FINGERPRINT
LABEL org.opencontainers.image.title="TDLib for Android" \
      org.opencontainers.image.description="Verified Android TDLib C JSON and JSONJava libraries for all four ABIs" \
      org.opencontainers.image.source="https://github.com/vigarepo2/TDLib" \
      org.opencontainers.image.url="https://hub.docker.com/r/vs69/tdlib" \
      org.opencontainers.image.version="${TDLIB_VERSION}" \
      org.opencontainers.image.revision="${TDLIB_COMMIT}" \
      org.opencontainers.image.licenses="BSL-1.0 AND Apache-2.0 AND BSD-3-Clause" \
      io.github.vigarepo2.tdlib.build-fingerprint="${BUILD_FINGERPRINT}"
COPY android-payload/ /opt/tdlib/android/
# A harmless placeholder lets docker create/docker cp work without an entrypoint;
# never docker run this data-only image. No executable or shell is included.
CMD ["/artifact-only-use-docker-cp"]
