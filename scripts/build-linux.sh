#!/usr/bin/env bash
# Called inside the Linux build stage; upstream/ must be an exact official checkout.
set -euo pipefail

source_dir=${1:-/upstream}
build_dir=${2:-/build}
prefix=${3:-/opt/tdlib}
: "${TDLIB_COMMIT:?Set TDLIB_COMMIT to the full official source commit}"
: "${TDLIB_VERSION:?Set TDLIB_VERSION to the version in upstream CMakeLists.txt}"
: "${BUILD_FINGERPRINT:?Set BUILD_FINGERPRINT to the distribution input hash}"
build_jobs=${BUILD_JOBS:-2}
[[ "$build_jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'BUILD_JOBS must be a positive integer' >&2; exit 1; }
[[ "$TDLIB_COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo 'TDLIB_COMMIT must be a full Git commit' >&2; exit 1; }
actual_commit=$(git -C "$source_dir" rev-parse HEAD)
[[ "$actual_commit" == "$TDLIB_COMMIT" ]] || { echo 'Source commit does not match requested commit' >&2; exit 1; }
git -C "$source_dir" diff --quiet
git -C "$source_dir" diff --cached --quiet

cmake -S "$source_dir" -B "$build_dir" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr/local \
    -DCMAKE_INSTALL_LIBDIR=lib \
    -DBUILD_TESTING=OFF \
    -DTD_INSTALL_SHARED_LIBRARIES=ON \
    -DTD_INSTALL_STATIC_LIBRARIES=ON \
    -DTD_ENABLE_LTO=OFF
cmake --build "$build_dir" --parallel "$build_jobs"
# Keep generated pkg-config prefixes correct for the final image while staging
# the relocatable CMake exports and libraries outside the builder's system paths.
cmake --install "$build_dir" --prefix "$prefix"
# Strip only shared objects. Static archives retain their linkable object code.
find "$prefix/lib" -maxdepth 1 -type f -name 'libtdjson.so*' -exec strip --strip-unneeded {} +
python3 /scripts/smoke-json.py "$prefix/lib/libtdjson.so" \
    --version "$TDLIB_VERSION" --commit "$TDLIB_COMMIT"

mkdir -p "$prefix/bin" "$prefix/share/tdlib/licenses" /opt/tdlib-runtime/lib
cc -O2 -Wall -Wextra -Werror /scripts/tdlib-info.c \
    -I"$prefix/include" -L"$prefix/lib" -Wl,-rpath,/usr/local/lib \
    -ltdjson -o "$prefix/bin/tdlib-info"
cp "$source_dir/LICENSE_1_0.txt" "$prefix/share/tdlib/licenses/TDLib.txt"
cp "$source_dir/sqlite/sqlite/LICENSE" "$prefix/share/tdlib/licenses/SQLCipher.txt"
cp "$source_dir/td/generate/tl-parser/LICENSE" "$prefix/share/tdlib/licenses/tl-parser.txt"
cp /distribution-license "$prefix/share/tdlib/licenses/distribution.txt"
cp /distribution-notices "$prefix/share/tdlib/licenses/THIRD_PARTY_NOTICES.md"
# Preserve SONAME symlinks; copying only libtdjson.so can duplicate or omit its target.
cp -a "$prefix"/lib/libtdjson.so* /opt/tdlib-runtime/lib/
cp -a "$prefix/bin" "$prefix/share" /opt/tdlib-runtime/

export TDLIB_COMMIT TDLIB_VERSION BUILD_FINGERPRINT
python3 - "$prefix/share/tdlib/build.json" <<'PY'
import json
import os
import pathlib
import platform
import sys

metadata = {
    "schema_version": 1,
    "upstream_repository": "https://github.com/tdlib/td",
    "upstream_version": os.environ["TDLIB_VERSION"],
    "upstream_commit": os.environ["TDLIB_COMMIT"],
    "build_fingerprint": os.environ["BUILD_FINGERPRINT"],
    "target_os": "linux",
    "target_architecture": platform.machine(),
    "libc": "musl" if pathlib.Path("/etc/alpine-release").exists() else "glibc",
    "distribution": pathlib.Path("/etc/os-release").read_text(),
}
pathlib.Path(sys.argv[1]).write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
PY
cp "$prefix/share/tdlib/build.json" /opt/tdlib-runtime/share/tdlib/build.json
