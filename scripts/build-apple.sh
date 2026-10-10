#!/usr/bin/env bash
# Native Xcode recipe: macOS universal + iOS arm64 + universal iOS simulator.
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/portable-common.sh"
portable_arguments apple "$@"
[[ $(uname -s) == Darwin ]] || { echo 'Apple packages require macOS with full Xcode installed.' >&2; exit 1; }
for tool in xcrun xcodebuild lipo install_name_tool; do
  command -v "$tool" >/dev/null || { echo "Missing Xcode tool: $tool" >&2; exit 1; }
done
MACOS_MINIMUM=$(config_get portable.macos_minimum)
IOS_MINIMUM=$(config_get portable.ios_minimum)
for sdk in macosx iphoneos iphonesimulator; do xcrun --sdk "$sdk" --show-sdk-path >/dev/null; done
fetch_openssl
generate_sources

build_slice() {
  local name=$1 sdk=$2 arch=$3 openssl_target=$4 minimum=$5
  local sdk_path crypto_source crypto_install build install minflag
  sdk_path=$(xcrun --sdk "$sdk" --show-sdk-path)
  crypto_source="$WORK/openssl-$name"
  crypto_install="$WORK/crypto-$name"
  build="$WORK/tdlib-$TDLIB_COMMIT-$name"
  install="$WORK/install-$name"
  case "$sdk" in
    macosx) minflag="-mmacosx-version-min=$minimum";;
    iphoneos) minflag="-miphoneos-version-min=$minimum";;
    iphonesimulator) minflag="-mios-simulator-version-min=$minimum";;
  esac
  # Each slice is independently configured; never reuse an OpenSSL tree for a different SDK.
  rm -rf "$crypto_source"
  mkdir -p "$crypto_source"
  tar -xzf "$OPENSSL_ARCHIVE" --strip-components=1 -C "$crypto_source"
  (
    cd "$crypto_source"
    export SDKROOT="$sdk_path"
    export CC="$(xcrun --sdk "$sdk" --find clang)"
    export CFLAGS="-arch $arch -isysroot $sdk_path $minflag"
    export LDFLAGS="$CFLAGS"
    ./Configure "$openssl_target" no-shared no-tests no-module \
      --prefix="$crypto_install" --openssldir="$crypto_install/ssl" --libdir=lib
    make -j"$PARALLEL"
    make install_sw
  )
  local platform_options=()
  if [[ "$sdk" == macosx ]]; then
    # Supplying system name also marks the non-host architecture as a cross build.
    platform_options=(-DCMAKE_SYSTEM_NAME=Darwin)
  else
    platform_options=(-DCMAKE_SYSTEM_NAME=iOS -DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_ALLOWED=NO)
  fi
  cmake -S "$SOURCE" -B "$build" -G Ninja \
    "${platform_options[@]}" -DCMAKE_BUILD_TYPE=Release \
    "-DCMAKE_OSX_SYSROOT=$sdk_path" "-DCMAKE_OSX_ARCHITECTURES=$arch" \
    "-DCMAKE_OSX_DEPLOYMENT_TARGET=$minimum" "-DCMAKE_INSTALL_PREFIX=$install" \
    "-DOPENSSL_ROOT_DIR=$crypto_install" "-DOPENSSL_INCLUDE_DIR=$crypto_install/include" \
    "-DOPENSSL_CRYPTO_LIBRARY=$crypto_install/lib/libcrypto.a" \
    "-DOPENSSL_SSL_LIBRARY=$crypto_install/lib/libssl.a" -DOPENSSL_USE_STATIC_LIBS=TRUE \
    -DTD_INSTALL_STATIC_LIBRARIES=OFF -DTD_INSTALL_SHARED_LIBRARIES=ON -DBUILD_TESTING=OFF
  cmake --build "$build" --target tdjson --parallel "$PARALLEL"
  cmake --install "$build"
  install_name_tool -id @rpath/libtdjson.dylib "$install/lib/libtdjson.dylib"
  # Reject accidentally shipping a dependency on a Homebrew/local OpenSSL library.
  if otool -L "$install/lib/libtdjson.dylib" | tail -n +2 | grep -E '/(opt/homebrew|usr/local|Users)/|lib(ssl|crypto)\.'; then
    echo 'Unexpected external OpenSSL/build-machine dependency in Apple package' >&2; exit 1
  fi
}

build_slice macos-arm64 macosx arm64 darwin64-arm64-cc "$MACOS_MINIMUM"
build_slice macos-x86_64 macosx x86_64 darwin64-x86_64-cc "$MACOS_MINIMUM"
build_slice ios-arm64 iphoneos arm64 ios64-xcrun "$IOS_MINIMUM"
build_slice simulator-arm64 iphonesimulator arm64 iossimulator-arm64-xcrun "$IOS_MINIMUM"
build_slice simulator-x86_64 iphonesimulator x86_64 iossimulator-x86_64-xcrun "$IOS_MINIMUM"

mkdir -p "$OUTPUT/macos/lib" "$OUTPUT/ios/lib" "$OUTPUT/ios-simulator/lib" "$OUTPUT/include" "$OUTPUT/licenses"
cp -R "$WORK/install-macos-arm64/include/." "$OUTPUT/include/"
lipo -create "$WORK/install-macos-arm64/lib/libtdjson.dylib" "$WORK/install-macos-x86_64/lib/libtdjson.dylib" \
  -output "$OUTPUT/macos/lib/libtdjson.dylib"
cp "$WORK/install-ios-arm64/lib/libtdjson.dylib" "$OUTPUT/ios/lib/"
lipo -create "$WORK/install-simulator-arm64/lib/libtdjson.dylib" "$WORK/install-simulator-x86_64/lib/libtdjson.dylib" \
  -output "$OUTPUT/ios-simulator/lib/libtdjson.dylib"
# Apple lipo treats every argument after -verify_arch as an architecture.
lipo "$OUTPUT/macos/lib/libtdjson.dylib" -verify_arch arm64 x86_64
lipo "$OUTPUT/ios/lib/libtdjson.dylib" -verify_arch arm64
lipo "$OUTPUT/ios-simulator/lib/libtdjson.dylib" -verify_arch arm64 x86_64
rm -rf "$OUTPUT/TDLib.xcframework"
xcodebuild -create-xcframework \
  -library "$OUTPUT/macos/lib/libtdjson.dylib" -headers "$OUTPUT/include" \
  -library "$OUTPUT/ios/lib/libtdjson.dylib" -headers "$OUTPUT/include" \
  -library "$OUTPUT/ios-simulator/lib/libtdjson.dylib" -headers "$OUTPUT/include" \
  -output "$OUTPUT/TDLib.xcframework"
python3 "$ROOT/scripts/verify-json.py" "$OUTPUT/macos/lib/libtdjson.dylib" --commit "$TDLIB_COMMIT"
cp "$WORK/openssl-macos-arm64/LICENSE.txt" "$OUTPUT/licenses/OpenSSL-Apache-2.0.txt"
cp "$SOURCE/td/generate/scheme/td_api.tl" "$OUTPUT/td_api.tl"
python3 - "$WORK/build-info.json" "$OPENSSL_VERSION" "$MACOS_MINIMUM" "$IOS_MINIMUM" <<'PY'
import json, pathlib, subprocess, sys
pathlib.Path(sys.argv[1]).write_text(json.dumps({
    'compiler': subprocess.check_output(['xcrun', 'clang', '--version'], text=True).splitlines()[0],
    'xcode': subprocess.check_output(['xcodebuild', '-version'], text=True).strip(),
    'openssl': sys.argv[2], 'minimum_macos': sys.argv[3], 'minimum_ios': sys.argv[4],
    'slices': {'macos': ['arm64', 'x86_64'], 'ios': ['arm64'], 'ios-simulator': ['arm64', 'x86_64']},
    'smoke_test': 'macOS host dylib loaded and JSON API executed; every slice architecture checked'
}, indent=2) + '\n')
PY
python3 "$ROOT/scripts/package.py" manifest --source "$SOURCE" --root "$OUTPUT" --platform apple --build-json "$WORK/build-info.json"
echo "Apple package ready: $OUTPUT"
