# syntax=docker/dockerfile:1.7
# Build from the repository root: docker build -f examples/go/Dockerfile -t tdlib-go .
ARG TDLIB_IMAGE=vs69/tdlib:debian-dev
ARG TDLIB_RUNTIME_IMAGE=vs69/tdlib:debian
FROM ${TDLIB_IMAGE} AS tdlib
FROM golang:1-bookworm AS builder
COPY --from=tdlib /usr/local/include/ /usr/local/include/
COPY --from=tdlib /usr/local/lib/ /usr/local/lib/
WORKDIR /src
COPY examples/go/ ./
RUN CGO_ENABLED=1 go build -trimpath -o /app .

FROM ${TDLIB_RUNTIME_IMAGE}
COPY --from=builder /app /usr/local/bin/tdlib-go
CMD ["tdlib-go"]
