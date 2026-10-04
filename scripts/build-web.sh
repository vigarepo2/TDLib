#!/usr/bin/env bash
# Build upstream's browser WebAssembly engine and tdweb package at one TDLib commit.
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/portable-common.sh"
portable_arguments web "$@"
[[ $(uname -s) == Linux ]] || { echo 'This recipe is verified by a Linux CI build host.' >&2; exit 1; }
for tool in emcc emcmake emmake emconfigure node npm; do
  command -v "$tool" >/dev/null || { echo "Missing tool: $tool. Activate the pinned Emscripten SDK first." >&2; exit 1; }
done
EMSDK_VERSION=$(config_get portable.emsdk_version)
ACTUAL_EMSDK=$(emcc --version | head -n 1)
[[ "$ACTUAL_EMSDK" == *" $EMSDK_VERSION "* ]] || {
  echo "Expected Emscripten $EMSDK_VERSION, got: $ACTUAL_EMSDK" >&2; exit 1;
}
fetch_openssl
generate_sources
CRYPTO_SOURCE="$WORK/openssl-source"
CRYPTO_INSTALL="$WORK/crypto"
rm -rf "$CRYPTO_SOURCE"
mkdir -p "$CRYPTO_SOURCE"
tar -xzf "$OPENSSL_ARCHIVE" --strip-components=1 -C "$CRYPTO_SOURCE"
(
  cd "$CRYPTO_SOURCE"
  # Upstream's example pins OpenSSL 1.1.0l. Use our checksummed supported LTS
  # OpenSSL instead, compiled for Emscripten rather than a host Linux library.
  export CC=emcc CXX=em++ AR=emar RANLIB=emranlib
  # emconfigure supplies absolute tool paths AND CROSS_COMPILE. OpenSSL would
  # concatenate them unless the prefix is explicitly cleared at configure time.
  emconfigure ./Configure linux-generic32 no-asm no-shared no-threads no-dso \
    no-module no-engine no-tests no-ui-console no-secure-memory no-afalgeng no-sock no-async \
    --cross-compile-prefix= \
    --prefix="$CRYPTO_INSTALL" --openssldir="$CRYPTO_INSTALL/ssl" --libdir=lib -Os
  emmake make -j"$PARALLEL" build_libs
  # Installing only headers/libraries avoids cross-executing OpenSSL tools.
  emmake make install_dev
)
BUILD="$WORK/tdlib-$TDLIB_COMMIT"
emcmake cmake -S "$SOURCE" -B "$BUILD" -G Ninja -DCMAKE_BUILD_TYPE=MinSizeRel \
  -DOPENSSL_FOUND=1 "-DOPENSSL_ROOT_DIR=$CRYPTO_INSTALL" \
  "-DOPENSSL_INCLUDE_DIR=$CRYPTO_INSTALL/include" \
  "-DOPENSSL_CRYPTO_LIBRARY=$CRYPTO_INSTALL/lib/libcrypto.a" \
  "-DOPENSSL_SSL_LIBRARY=$CRYPTO_INSTALL/lib/libssl.a" \
  "-DOPENSSL_LIBRARIES=$CRYPTO_INSTALL/lib/libssl.a;$CRYPTO_INSTALL/lib/libcrypto.a" \
  "-DOPENSSL_VERSION=$OPENSSL_VERSION" -DBUILD_TESTING=OFF
cmake --build "$BUILD" --target td_wasm --parallel "$PARALLEL"
mkdir -p "$OUTPUT/wasm" "$OUTPUT/licenses"
cp "$BUILD/td_wasm.js" "$BUILD/td_wasm.wasm" "$OUTPUT/wasm/"
node "$ROOT/scripts/smoke-web.cjs" "$OUTPUT/wasm"

# Work on a copy: never rewrite the upstream checkout or its dependency lock.
WRAPPER="$WORK/tdweb"
rm -rf "$WRAPPER"
mkdir -p "$WRAPPER"
cp -R "$SOURCE/example/web/tdweb/." "$WRAPPER/"
mkdir -p "$WRAPPER/src/prebuilt/release"
cp "$OUTPUT/wasm/td_wasm.js" "$OUTPUT/wasm/td_wasm.wasm" "$WRAPPER/src/prebuilt/release/"
(
  cd "$WRAPPER"
  npm ci --ignore-scripts --no-audit --no-fund
  # Upstream currently uses webpack 4. Its MD4 bundler needs this Node >=17 flag.
  # It affects only build tooling; it is not enabled in the browser runtime.
  NODE_OPTIONS=--openssl-legacy-provider npm run build
  npm pack --ignore-scripts --pack-destination "$OUTPUT"
)
cp -R "$WRAPPER/dist" "$OUTPUT/"
cp "$WRAPPER/README.md" "$OUTPUT/TDWEB-USAGE.md"
cp "$CRYPTO_SOURCE/LICENSE.txt" "$OUTPUT/licenses/OpenSSL-Apache-2.0.txt"
cp "$SOURCE/td/generate/scheme/td_api.tl" "$OUTPUT/td_api.tl"
# Preserve exact wrapper dependencies and license metadata; npm tarball is upstream MIT.
cp "$WRAPPER/package.json" "$WRAPPER/package-lock.json" "$OUTPUT/"
python3 - "$OUTPUT/licenses/emscripten" <<'PY'
import pathlib, shutil, sys
compiler = pathlib.Path(shutil.which('emcc')).resolve().parent
destination = pathlib.Path(sys.argv[1])
license_file = compiler / 'LICENSE'
if not license_file.is_file():
    raise SystemExit('Emscripten license file is missing from the activated SDK')
destination.mkdir(parents=True, exist_ok=True)
shutil.copy2(license_file, destination / 'LICENSE')
for file in sorted((compiler / 'system/lib').rglob('*')):
    if file.is_file() and file.name.lower().startswith(('license', 'licence', 'copying', 'copyright', 'notice')):
        target = destination / file.relative_to(compiler)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, target)
PY
cat > "$OUTPUT/licenses/tdweb-MIT-notice.txt" <<'NOTICE'
The upstream tdweb package declares the MIT license. Its package.json, exact
package-lock.json, author and source repository are included in this package.
TDLib's native/WebAssembly implementation is distributed under Boost 1.0.
The JavaScript wrapper's third-party bundled dependencies retain their own
licenses; see npm-dependency-licenses.txt and package-lock.json.
NOTICE
python3 - "$WRAPPER/node_modules" "$OUTPUT/licenses/npm-dependency-licenses.txt" <<'PY'
import pathlib, sys
root = pathlib.Path(sys.argv[1])
output = pathlib.Path(sys.argv[2])
with output.open('w') as target:
    for file in sorted(root.rglob('*')):
        if file.is_file() and file.name.lower().startswith(('license', 'licence', 'copying', 'notice')):
            target.write(f'\n===== {file.relative_to(root)} =====\n')
            target.write(file.read_text(errors='replace') + '\n')
PY
python3 - "$WORK/build-info.json" "$EMSDK_VERSION" "$OPENSSL_VERSION" "$WRAPPER/package-lock.json" <<'PY'
import hashlib, json, pathlib, subprocess, sys
pathlib.Path(sys.argv[1]).write_text(json.dumps({
    'emscripten': sys.argv[2], 'openssl': sys.argv[3],
    'node': subprocess.check_output(['node', '--version'], text=True).strip(),
    'npm': subprocess.check_output(['npm', '--version'], text=True).strip(),
    'npm_lock_sha256': hashlib.sha256(pathlib.Path(sys.argv[4]).read_bytes()).hexdigest(),
    'interface': 'Official tdweb browser wrapper and raw Emscripten JSON ABI',
    'smoke_test': 'Instantiated actual WebAssembly and executed getTextEntities under Node'
}, indent=2) + '\n')
PY
python3 "$ROOT/scripts/package-common.py" --source "$SOURCE" --root "$OUTPUT" --platform web --build-json "$WORK/build-info.json"
echo "Browser WebAssembly package ready: $OUTPUT"
