# syntax=docker/dockerfile:1.7
# Build from the repository root: docker build -f examples/python/Dockerfile -t tdlib-python .
ARG TDLIB_IMAGE=vs69/tdlib:debian
FROM ${TDLIB_IMAGE} AS tdlib
FROM python:3.13-slim-bookworm
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then set -- -o Acquire::https::CaInfo=/run/secrets/proxy_ca; fi \
    && apt-get "$@" update \
    && apt-get "$@" install -y --no-install-recommends ca-certificates libssl3 libstdc++6 zlib1g \
    && rm -rf /var/lib/apt/lists/*
COPY --from=tdlib /usr/local/lib/ /usr/local/lib/
COPY --from=tdlib /usr/local/share/tdlib/ /usr/local/share/tdlib/
RUN ldconfig && useradd --uid 10001 --create-home app
WORKDIR /app
COPY examples/python/main.py ./main.py
USER app
CMD ["python", "main.py"]
