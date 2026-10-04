#!/usr/bin/env bash
# Bootstrap the official, Java 17-compatible SDK manager on Linux CI runners.
set -euo pipefail

TOOLS_VERSION=19.0
TOOLS_ARCHIVE=commandlinetools-linux-13114758_latest.zip
TOOLS_SHA256=7ec965280a073311c339e571cd5de778b9975026cfcbe79f2b1cdcb1e15317ee
SDK=${ANDROID_HOME:-${ANDROID_SDK_ROOT:-${RUNNER_TEMP:-}/teleplay-android-sdk}}
PACKAGES=()
STAGING=''

usage() {
  cat <<'USAGE'
Usage: tools/install-android-sdk.sh [--sdk-root directory] package [package ...]
Examples:
  tools/install-android-sdk.sh 'ndk;28.2.13676358' 'cmake;3.22.1'
  tools/install-android-sdk.sh 'platforms;android-36' 'build-tools;36.0.0'
Requires Linux x86_64, Java 17+, Curl, Unzip, and SHA-256 tools.
Installs checksum-pinned official command-line tools 19.0, accepts SDK licenses,
and exports ANDROID_HOME, ANDROID_SDK_ROOT and tool paths in GitHub Actions.
Use ANDROID_HOME or --sdk-root for local builds. No credentials are required.
USAGE
}
while (($#)); do
  case "$1" in
    --sdk-root)
      (($# >= 2)) || { usage >&2; exit 2; }
      SDK=$2; shift 2;;
    -h|--help) usage; exit 0;;
    *)
      [[ "$1" =~ ^(ndk\;[0-9.]+|cmake\;[0-9.]+|platforms\;android-[0-9]+|build-tools\;[0-9.]+)$ ]] || {
        printf 'Unsupported SDK package: %s\n' "$1" >&2; exit 2;
      }
      PACKAGES+=("$1"); shift;;
  esac
done
((${#PACKAGES[@]})) || { usage >&2; exit 2; }
[[ -n "$SDK" && "$SDK" != /teleplay-android-sdk && "$SDK" != *$'\n'* && "$SDK" != *$'\r'* ]] || {
  echo 'Set ANDROID_HOME or pass --sdk-root to a writable SDK directory' >&2; exit 2;
}
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || { echo 'A Linux x86_64 SDK host is required' >&2; exit 1; }
for tool in java curl unzip sha256sum mktemp; do
  command -v "$tool" >/dev/null || { printf 'Required SDK bootstrap tool is missing: %s\n' "$tool" >&2; exit 1; }
done
mkdir -p -- "$SDK/cmdline-tools"
SDK=$(cd -- "$SDK" && pwd -P)
TOOLS="$SDK/cmdline-tools/$TOOLS_VERSION"
MANAGER="$TOOLS/bin/sdkmanager"
revision() {
  local property value
  [[ -f "$1/source.properties" ]] || return 1
  while IFS='=' read -r property value; do
    if [[ "${property//[[:space:]]/}" == Pkg.Revision ]]; then
      printf '%s' "${value//[[:space:]]/}"; return 0
    fi
  done < "$1/source.properties"
  return 1
}
cleanup() { [[ -z "$STAGING" ]] || rm -rf -- "$STAGING"; }
trap cleanup EXIT
STAGING=$(mktemp -d "$SDK/.teleplay-sdk-XXXXXXXX")
if [[ ! -e "$TOOLS" ]]; then
  printf 'Downloading official Android command-line tools %s\n' "$TOOLS_VERSION"
  curl --fail --location --retry 3 --proto '=https' --proto-redir '=https' --tlsv1.2 \
    "https://dl.google.com/android/repository/$TOOLS_ARCHIVE" --output "$STAGING/tools.zip"
  printf '%s  %s\n' "$TOOLS_SHA256" "$STAGING/tools.zip" | sha256sum --check --status || {
    echo 'Android command-line tools SHA-256 mismatch; refusing installation' >&2; exit 1;
  }
  unzip -q "$STAGING/tools.zip" -d "$STAGING/extracted"
  [[ $(revision "$STAGING/extracted/cmdline-tools") == "$TOOLS_VERSION" ]] || {
    echo 'Android command-line tools archive revision mismatch' >&2; exit 1;
  }
  mv -- "$STAGING/extracted/cmdline-tools" "$TOOLS"
fi
[[ -x "$MANAGER" && $(revision "$TOOLS") == "$TOOLS_VERSION" ]] || {
  echo 'Pinned Android command-line tools are incomplete or have the wrong revision' >&2; exit 1;
}
# A finite input file avoids a yes|sdkmanager pipeline failing with SIGPIPE.
for ((answer=0; answer<256; answer++)); do printf 'y\n'; done > "$STAGING/license-answers"
export ANDROID_HOME="$SDK" ANDROID_SDK_ROOT="$SDK"
if ! "$MANAGER" --sdk_root="$SDK" --licenses < "$STAGING/license-answers" > "$STAGING/licenses.log" 2>&1; then
  cat "$STAGING/licenses.log" >&2
  echo 'Android SDK license acceptance failed' >&2; exit 1
fi
"$MANAGER" --sdk_root="$SDK" --install "${PACKAGES[@]}" < "$STAGING/license-answers"
for package in "${PACKAGES[@]}"; do
  directory="$SDK/${package//;/\/}"
  [[ -f "$directory/source.properties" ]] || {
    printf 'SDK manager did not install the requested package: %s\n' "$package" >&2; exit 1;
  }
  if [[ "$package" != platforms\;* && $(revision "$directory") != "${package#*;}" ]]; then
    printf 'Installed SDK package revision mismatch: %s\n' "$package" >&2; exit 1
  fi
done
if [[ -n "${GITHUB_ENV:-}" ]]; then
  printf 'ANDROID_HOME=%s\nANDROID_SDK_ROOT=%s\n' "$SDK" "$SDK" >> "$GITHUB_ENV"
fi
if [[ -n "${GITHUB_PATH:-}" ]]; then
  printf '%s\n' "$TOOLS/bin" >> "$GITHUB_PATH"
  [[ ! -d "$SDK/cmake/3.22.1/bin" ]] || printf '%s\n' "$SDK/cmake/3.22.1/bin" >> "$GITHUB_PATH"
fi
printf 'Ready: official SDK manager %s at %s\n' "$TOOLS_VERSION" "$MANAGER"
