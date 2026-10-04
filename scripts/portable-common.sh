#!/usr/bin/env bash
# Shared prerequisites for native Apple and browser recipes. Source from bash.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SOURCE="$ROOT/upstream"
PARALLEL=${TDLIB_JOBS:-${BUILD_JOBS:-2}}
OUTPUT=
WORK=

portable_arguments() {
  local target=$1; shift
  OUTPUT="$ROOT/dist/$target"
  WORK="$ROOT/.native-build/$target"
  while (($#)); do
    case "$1" in
      --source|--output|--work-dir|--parallel)
        (($# >= 2)) || { echo "Missing value: $1" >&2; exit 2; }
        case "$1" in --source) SOURCE=$2;; --output) OUTPUT=$2;; --work-dir) WORK=$2;; --parallel) PARALLEL=$2;; esac
        shift 2;;
      --help|-h)
        echo "Usage: $0 [--source upstream] [--output dist/$target] [--work-dir .native-build/$target] [--parallel 2]"
        exit 0;;
      *) echo "Unknown argument: $1" >&2; exit 2;;
    esac
  done
  case "$PARALLEL" in 1|2|3|4) ;; *) echo 'Parallelism must be between 1 and 4' >&2; exit 2;; esac
  for command in git cmake ninja python3 curl perl make gperf; do
    command -v "$command" >/dev/null || { echo "Missing required tool: $command" >&2; exit 1; }
  done
  SOURCE=$(cd -- "$SOURCE" && pwd -P)
  TDLIB_COMMIT=$(git -C "$SOURCE" rev-parse HEAD)
  [[ "$TDLIB_COMMIT" =~ ^[a-f0-9]{40}$ ]] || { echo 'Invalid official TDLib checkout' >&2; exit 1; }
  git -C "$SOURCE" diff --quiet
  git -C "$SOURCE" diff --cached --quiet
  mkdir -p "$OUTPUT" "$WORK"
  OUTPUT=$(cd -- "$OUTPUT" && pwd -P)
  WORK=$(cd -- "$WORK" && pwd -P)
  OPENSSL_VERSION=$(config_get android.openssl.version)
  OPENSSL_SHA256=$(config_get android.openssl.sha256)
  [[ "$OPENSSL_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ && "$OPENSSL_SHA256" =~ ^[a-f0-9]{64}$ ]] || {
    echo 'Invalid pinned OpenSSL configuration' >&2; exit 1;
  }
}

config_get() {
  python3 - "$ROOT/config/build.json" "$1" <<'PY'
import json, sys
value = json.load(open(sys.argv[1]))
for field in sys.argv[2].split('.'):
    value = value[field]
print(value)
PY
}

fetch_openssl() {
  OPENSSL_ARCHIVE="$WORK/openssl-$OPENSSL_VERSION.tar.gz"
  if [[ ! -f "$OPENSSL_ARCHIVE" ]]; then
    curl --fail --location --retry 3 --proto '=https' --proto-redir '=https' \
      "https://github.com/openssl/openssl/releases/download/openssl-$OPENSSL_VERSION/openssl-$OPENSSL_VERSION.tar.gz" \
      --output "$OPENSSL_ARCHIVE.part"
    mv "$OPENSSL_ARCHIVE.part" "$OPENSSL_ARCHIVE"
  fi
  python3 - "$OPENSSL_ARCHIVE" "$OPENSSL_SHA256" <<'PY'
import hashlib, pathlib, sys
actual = hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest()
if actual != sys.argv[2]:
    raise SystemExit('OpenSSL archive SHA256 mismatch; refusing to compile')
PY
}

generate_sources() {
  cmake -S "$SOURCE" -B "$WORK/generate-$TDLIB_COMMIT" -G Ninja \
    -DTD_GENERATE_SOURCE_FILES=ON -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF
  cmake --build "$WORK/generate-$TDLIB_COMMIT" --parallel "$PARALLEL"
}
