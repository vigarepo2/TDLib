#!/usr/bin/env bash
# Build both official Android JSON interfaces from an exact local TDLib checkout.
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
ABI=all
SOURCE=
CONFIG="$ROOT/config/build.json"
OUTPUT="$ROOT/dist/android"
PARALLEL=2
CACHE=${TDLIB_BUILD_ROOT:-"$ROOT/.native-build"}

usage() {
  cat <<'USAGE'
Usage: scripts/build-android.sh --source checkout --abi all|armeabi-v7a|arm64-v8a|x86|x86_64
                                --output directory [--config config/build.json]
                                [--parallel 1|2|3|4] [--work-dir directory]
Requires a clean official TDLib checkout, Linux x86_64, the configured Android NDK,
CMake >= 3.22, Ninja, a host C++ compiler, gperf, Perl, Make, Curl, and Python 3.
Outputs jniLibs/<abi>/libtdjson.so, libtdjsonjava.so, headers, and license texts.
No Android SDK, NDK, private keys or credentials are included in the final image.
USAGE
}
while (($#)); do
  case "$1" in
    --abi|--output|--parallel|--work-dir|--source|--config)
      (($# >= 2)) || { usage >&2; exit 2; }
      case "$1" in
        --source) SOURCE=$2;; --config) CONFIG=$2;; --abi) ABI=$2;; --output) OUTPUT=$2;; --parallel) PARALLEL=$2;; --work-dir) CACHE=$2;;
      esac
      shift 2;;
    -h|--help) usage; exit 0;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2;;
  esac
done
[[ -n "$SOURCE" && -d "$SOURCE/.git" ]] || { echo '--source must be a clean official TDLib Git checkout' >&2; exit 2; }
SOURCE=$(cd -- "$SOURCE" && pwd -P)
TDLIB_COMMIT=$(git -C "$SOURCE" rev-parse HEAD)
[[ "$TDLIB_COMMIT" =~ ^[a-f0-9]{40}$ ]] || { echo 'Invalid TDLib source commit' >&2; exit 1; }
git -C "$SOURCE" diff --quiet && git -C "$SOURCE" diff --cached --quiet || {
  echo 'Tracked TDLib sources have local modifications; use a clean checkout' >&2; exit 1;
}
# Data is printed as one validated value per line; never eval configuration text.
mapfile -t PINS < <(python3 "$ROOT/scripts/package-android.py" pins --config "$CONFIG")
((${#PINS[@]} == 4)) || { echo 'Invalid Android build pins' >&2; exit 1; }
NDK_VERSION=${PINS[0]}
ANDROID_API=${PINS[1]}
OPENSSL_VERSION=${PINS[2]}
OPENSSL_SHA256=${PINS[3]}
case "$ABI" in all|armeabi-v7a|arm64-v8a|x86|x86_64) ;; *) echo 'Unsupported ABI' >&2; exit 2;; esac
case "$PARALLEL" in 1|2|3|4) ;; *) echo '--parallel must be between 1 and 4' >&2; exit 2;; esac
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || { echo 'A Linux x86_64 build host is required' >&2; exit 1; }
SDK=${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}
[[ -n "$SDK" ]] || { echo 'Set ANDROID_HOME to your Android SDK directory' >&2; exit 1; }
NDK="$SDK/ndk/$NDK_VERSION"
ACTUAL_NDK_VERSION=''
if [[ -f "$NDK/source.properties" ]]; then
  while IFS='=' read -r property value; do
    [[ "${property//[[:space:]]/}" != Pkg.Revision ]] || ACTUAL_NDK_VERSION=${value//[[:space:]]/}
  done < "$NDK/source.properties"
fi
[[ "$ACTUAL_NDK_VERSION" == "$NDK_VERSION" ]] || {
  printf 'Install the pinned NDK with sdkmanager "ndk;%s"\n' "$NDK_VERSION" >&2; exit 1;
}
LLVM="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin"
[[ -x "$LLVM/clang" ]] || { echo 'Pinned NDK Linux compiler is missing' >&2; exit 1; }
if [[ -x "$SDK/cmake/3.22.1/bin/cmake" ]]; then
  export PATH="$SDK/cmake/3.22.1/bin:$PATH"
fi
for tool in git curl python3 cmake ninja gperf perl make c++ sha256sum; do
  command -v "$tool" >/dev/null || { printf 'Required tool is missing: %s\n' "$tool" >&2; exit 1; }
done
python3 - <<'PY'
import re, subprocess
version = tuple(map(int, re.search(r'cmake version (\d+)\.(\d+)\.(\d+)',
                                  subprocess.check_output(['cmake', '--version'], text=True)).groups()))
if version < (3, 22, 0):
    raise SystemExit('CMake 3.22 or newer is required')
PY
mkdir -p -- "$CACHE" "$OUTPUT"
CACHE=$(cd -- "$CACHE" && pwd -P)
OUTPUT=$(cd -- "$OUTPUT" && pwd -P)
# Keep source generation and caches exclusive when multiple jobs use one directory.
command -v flock >/dev/null || { echo 'flock is required for cache safety' >&2; exit 1; }
exec 9>"$CACHE/.lock"
flock 9
TARBALL="$CACHE/openssl-$OPENSSL_VERSION.tar.gz"
if [[ ! -f "$TARBALL" ]]; then
  curl --fail --location --retry 3 --proto '=https' --proto-redir '=https' --tlsv1.2 \
    "https://github.com/openssl/openssl/releases/download/openssl-$OPENSSL_VERSION/openssl-$OPENSSL_VERSION.tar.gz" \
    --output "$TARBALL.part"
  mv -- "$TARBALL.part" "$TARBALL"
fi
printf '%s  %s\n' "$OPENSSL_SHA256" "$TARBALL" | sha256sum --check --status || {
  echo 'OpenSSL archive SHA-256 mismatch; refusing to build' >&2; exit 1;
}
# A recipe change must not reuse an OpenSSL completion marker or native objects
# built with different flags, even when dependency versions stay unchanged.
BUILD_RECIPE_SHA256=$(cat -- "${BASH_SOURCE[0]}" "$CONFIG" "$ROOT/scripts/package-android.py" | sha256sum)
BUILD_RECIPE_SHA256=${BUILD_RECIPE_SHA256%% *}
BUILD_KEY="openssl$OPENSSL_VERSION-ndk$NDK_VERSION-api$ANDROID_API-recipe$BUILD_RECIPE_SHA256"
HOST_BUILD="$CACHE/host-$TDLIB_COMMIT-recipe$BUILD_RECIPE_SHA256"
printf 'Generating official TDLib source files (%s)\n' "$TDLIB_COMMIT"
cmake -S "$SOURCE/example/android" -B "$HOST_BUILD" -G Ninja \
  -DTD_ANDROID_JSON_JAVA=ON -DTD_GENERATE_SOURCE_FILES=ON -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build "$HOST_BUILD" --parallel "$PARALLEL"
ABIS=("$ABI")
[[ "$ABI" != all ]] || ABIS=(arm64-v8a armeabi-v7a x86_64 x86)
for CURRENT_ABI in "${ABIS[@]}"; do
  case "$CURRENT_ABI" in
    arm64-v8a) OPENSSL_TARGET=android-arm64;;
    armeabi-v7a) OPENSSL_TARGET=android-arm;;
    x86_64) OPENSSL_TARGET=android-x86_64;;
    x86) OPENSSL_TARGET=android-x86;;
  esac
  SSL_PREFIX="$CACHE/openssl-install-$BUILD_KEY/$CURRENT_ABI"
  SSL_BUILD="$CACHE/openssl-build-$BUILD_KEY/$CURRENT_ABI"
  if [[ ! -f "$SSL_PREFIX/.complete" ]]; then
    mkdir -p -- "$SSL_BUILD" "$SSL_PREFIX"
    tar -xzf "$TARBALL" --strip-components=1 -C "$SSL_BUILD"
    printf 'Building OpenSSL %s for %s\n' "$OPENSSL_VERSION" "$CURRENT_ABI"
    (
      cd -- "$SSL_BUILD"
      export ANDROID_NDK_ROOT="$NDK" ANDROID_NDK_HOME="$NDK"
      export PATH="$LLVM:$PATH"
      export CFLAGS='-O2 -fPIC -ffunction-sections -fdata-sections'
      perl ./Configure "$OPENSSL_TARGET" -U__ANDROID_API__ -D__ANDROID_API__="$ANDROID_API" \
        no-shared no-tests no-apps no-docs no-module --prefix="$SSL_PREFIX" --libdir=lib
      make -j"$PARALLEL"
      make install_sw
    )
    [[ -s "$SSL_PREFIX/lib/libcrypto.a" && -s "$SSL_PREFIX/lib/libssl.a" ]] || { echo 'OpenSSL static libraries missing' >&2; exit 1; }
    touch "$SSL_PREFIX/.complete"
  fi
  BUILD="$CACHE/android-$BUILD_KEY-$TDLIB_COMMIT/$CURRENT_ABI"
  printf 'Building TDLib JSON and JSONJava for %s\n' "$CURRENT_ABI"
  cmake -S "$SOURCE/example/android" -B "$BUILD" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
    -DANDROID_ABI="$CURRENT_ABI" -DANDROID_PLATFORM="android-$ANDROID_API" \
    -DANDROID_STL=c++_static -DANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES=ON \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS_RELEASE='-O2 -DNDEBUG' \
    -DCMAKE_CXX_FLAGS_RELEASE='-O2 -DNDEBUG' \
    -DCMAKE_SHARED_LINKER_FLAGS='-Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384' \
    -DOPENSSL_ROOT_DIR="$SSL_PREFIX" -DOPENSSL_USE_STATIC_LIBS=TRUE \
    -DOPENSSL_CRYPTO_LIBRARY="$SSL_PREFIX/lib/libcrypto.a" \
    -DOPENSSL_SSL_LIBRARY="$SSL_PREFIX/lib/libssl.a" -DOPENSSL_INCLUDE_DIR="$SSL_PREFIX/include" \
    -DTD_ANDROID_JSON_JAVA=ON -DBUILD_TESTING=OFF -DTD_ENABLE_LTO=OFF
  cmake --build "$BUILD" --target tdjni tdjson --parallel "$PARALLEL"
  mkdir -p -- "$OUTPUT/jniLibs/$CURRENT_ABI" "$OUTPUT/include/td/telegram" "$OUTPUT/licenses"
  for NAME in libtdjsonjava.so libtdjson.so; do
    LIBRARY="$BUILD/$NAME"
    [[ "$NAME" != libtdjson.so ]] || LIBRARY="$BUILD/td/libtdjson.so"
    [[ -s "$LIBRARY" ]] || { printf 'Native build did not produce %s\n' "$NAME" >&2; exit 1; }
    "$LLVM/llvm-strip" --strip-debug --strip-unneeded "$LIBRARY" -o "$OUTPUT/jniLibs/$CURRENT_ABI/$NAME.part"
    python3 "$ROOT/scripts/package-android.py" verify-library --abi "$CURRENT_ABI" \
      --kind "$NAME" "$OUTPUT/jniLibs/$CURRENT_ABI/$NAME.part"
    mv -- "$OUTPUT/jniLibs/$CURRENT_ABI/$NAME.part" "$OUTPUT/jniLibs/$CURRENT_ABI/$NAME"
  done
  install -m 644 "$BUILD/td/td/telegram/tdjson_export.h" "$OUTPUT/include/td/telegram/tdjson_export.h"
  install -m 644 "$SOURCE/td/telegram/td_json_client.h" "$SOURCE/td/telegram/td_log.h" "$OUTPUT/include/td/telegram/"
  install -m 644 "$SSL_BUILD/LICENSE.txt" "$OUTPUT/licenses/OpenSSL.LICENSE.txt"
  install -m 644 "$NDK/NOTICE" "$OUTPUT/licenses/Android-NDK.NOTICE.txt"
  printf 'Ready: Android %s JSON C API and JSONJava\n' "$CURRENT_ABI"
done
