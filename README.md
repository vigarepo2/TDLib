# TDLib

Prebuilt TDLib libraries for Linux, Android, Windows, macOS, iOS and WebAssembly.

[![Build and publish](https://github.com/vigarepo2/TDLib/actions/workflows/build-and-publish.yml/badge.svg)](https://github.com/vigarepo2/TDLib/actions/workflows/build-and-publish.yml)
[![Validate](https://github.com/vigarepo2/TDLib/actions/workflows/validate.yml/badge.svg)](https://github.com/vigarepo2/TDLib/actions/workflows/validate.yml)
[![License](https://img.shields.io/badge/license-BSL--1.0-blue)](https://github.com/vigarepo2/TDLib/blob/main/LICENSE)

[Docker Hub](https://hub.docker.com/r/vs69/tdlib) · [Downloads](https://github.com/vigarepo2/TDLib/releases/tag/latest) · [Build history](https://github.com/vigarepo2/TDLib/actions) · [Official TDLib documentation](https://core.telegram.org/tdlib)

Use these packages to integrate Telegram's native engine without compiling it in every application build. Each publication records its upstream commit, build configuration and checksums. This is an independent distribution of [tdlib/td](https://github.com/tdlib/td), maintained by [vigarepo2](https://github.com/vigarepo2).

**Contents:** [Packages](https://github.com/vigarepo2/TDLib#packages) · [Linux](https://github.com/vigarepo2/TDLib#linux) · [Android](https://github.com/vigarepo2/TDLib#android) · [Windows, Apple and web](https://github.com/vigarepo2/TDLib#windows-apple-and-web) · [Updates](https://github.com/vigarepo2/TDLib#updates-and-verification) · [Publishing](https://github.com/vigarepo2/TDLib#publishing)

## Packages

| Docker tag | Platforms | Contents |
| --- | --- | --- |
| `latest`, `debian` | Linux amd64 / arm64 | Debian runtime, JSON shared library |
| `alpine` | Linux amd64 / arm64 | Alpine runtime, JSON shared library |
| `dev`, `debian-dev` | Linux amd64 / arm64 | Debian runtime, headers, static libraries and CMake exports |
| `alpine-dev` | Linux amd64 / arm64 | Alpine runtime, headers, static libraries and CMake exports |
| `android` | arm64-v8a / armeabi-v7a / x86 / x86_64 | JSON C and Java/JNI libraries, headers, sources and manifest |
| `packages` | Android, Windows x64, macOS, iOS, browser | Platform archives and checksums |

All tags use **`vs69/tdlib`**. The `android` and `packages` images carry files for extraction with `docker cp`; they contain no runnable application. Direct downloads are available from the [rolling release](https://github.com/vigarepo2/TDLib/releases/tag/latest).

TDLib supplies networking, encryption, local storage and updates. Your application supplies its interface, Telegram authorization and session handling. These packages do not start a bot, HTTP service or streaming server.

## Linux

```sh
docker pull vs69/tdlib:latest
docker run --rm vs69/tdlib:latest
```

The command loads TDLib, prints its version and commit, checks the JSON interface, and exits without a Telegram login.

| Setting | Value |
| --- | --- |
| Shared library | `/usr/local/lib/libtdjson.so` |
| Library environment variable | `TDLIB_LIBRARY_PATH` |
| Runtime user | `tdlib` — UID/GID 10001 |
| Working directory | `/data` |
| Provenance | `/usr/local/share/tdlib/build.json` |
| Notices | `/usr/local/share/tdlib/licenses/` |
| Debian base | Debian 12 / bookworm, glibc 2.36 |
| Alpine base | Alpine 3.23, musl |

Use the matching runtime image as your application's base. Persist session data in a writable volume. When copying the library elsewhere, match its CPU architecture, libc, C++ runtime, OpenSSL and zlib dependencies. Debian and Alpine libraries are not interchangeable.

The development images include compilers and TDLib's CMake package. C/C++ applications can use `find_package(Td REQUIRED CONFIG)` and link `Td::TdJson` or `Td::TdJsonStatic`. Other native languages can use a compatible JSON binding or FFI adapter; keep that adapter aligned with the packaged API schema.

## Android

The Android package targets **API 24+**, uses **NDK 28.2.13676358** and **OpenSSL 3.5.9**, and checks native ELF alignment for **16 KB pages** across all four ABIs. The consuming application's Gradle configuration and finished APK must also support the devices and page sizes it targets.

### Gradle integration

Download [`tdlib-android.aar`](https://github.com/vigarepo2/TDLib/releases/download/latest/tdlib-android.aar), place it in `app/libs`, and add:

```kotlin
dependencies {
    implementation(files("libs/tdlib-android.aar"))
}
```

Set `minSdk` to at least 24. The AAR contains `org.drinkless.tdlib.JsonClient`, four JNI libraries, consumer R8 rules and license assets. Do not also copy the same classes or JNI libraries into the application.

```kotlin
import org.drinkless.tdlib.JsonClient

val version = JsonClient.execute("""{"@type":"getOption","name":"version"}""")
```

This is the **JSON Java interface**, which exchanges JSON strings. The separate generated `TdApi` class interface is not included. Most TDLib requests are asynchronous: receive updates on a dedicated thread and handle authorization states in the application. Do not call `JsonClient.receive` concurrently from multiple threads or block the Android UI thread.

### Native files

For C/FFI integration or manual JNI packaging:

```sh
docker pull --platform linux/amd64 vs69/tdlib:android
docker create --platform linux/amd64 --name tdlib-android vs69/tdlib:android
mkdir -p tdlib-android
docker cp tdlib-android:/opt/tdlib/android/. ./tdlib-android/
docker rm tdlib-android
(cd tdlib-android && sha256sum -c checksums.sha256)
```

The file container uses `linux/amd64` on every host; its contents still include all Android ABIs. Nothing is executed during extraction. The same payload is available as [`tdlib-android.tar.gz`](https://github.com/vigarepo2/TDLib/releases/download/latest/tdlib-android.tar.gz).

| Path | Purpose |
| --- | --- |
| `jniLibs/<ABI>/libtdjson.so` | Native JSON C interface |
| `jniLibs/<ABI>/libtdjsonjava.so` | Self-contained JSON Java/JNI interface |
| `sources/JsonClient.java` | Matching upstream Java adapter |
| `sources/td_api.tl` | Matching API schema |
| `include/td/telegram/` | C headers |
| `manifest.json`, `checksums.sha256` | Source identity, build contract and file integrity |
| `licenses/` | Included component notices |

Manual Java/Kotlin integration needs `JsonClient.java` and `libtdjsonjava.so`, with R8 rules preserving `org.drinkless.tdlib.JsonClient` and its nested classes. It does not also need `libtdjson.so`. Keep native libraries, bindings and schemas from the same package.

The Android Docker tag is published as soon as its package checks pass. The AAR and archive on GitHub update when the complete platform release succeeds, so their source commits can temporarily differ. Consumers such as [TelePlay](https://github.com/vigarepo2/TelePlay) should use a verified image digest and compare the package manifest with their expected engine inputs.

## Windows, Apple and web

Download the appropriate archive from the [release page](https://github.com/vigarepo2/TDLib/releases/tag/latest), then extract it into its own directory.

| Download | Contents and requirements |
| --- | --- |
| `tdlib-windows-x64.tar.gz` | `bin/tdjson.dll`, headers and import library. Requires the Microsoft Visual C++ x64 Redistributable; OpenSSL and zlib are linked statically. |
| `tdlib-apple.tar.gz` | `TDLib.xcframework`, C headers and dylibs: macOS 11+ universal, iOS 13+ arm64, and universal iOS simulator. The consuming Xcode app handles embedding and signing. |
| `tdlib-web.tar.gz` | Upstream `tdweb-*.tgz`, `dist/`, raw WebAssembly, wrapper instructions and dependency lock. Install the local npm archive and serve every `dist/` asset together over HTTPS. |

Windows ARM64, Windows x86, watchOS, tvOS, visionOS and Catalyst are not included. Native packages require platform-specific bindings; the browser uses the dedicated `tdweb` wrapper. Serve `.wasm` as `application/wasm` and follow the bundled `TDWEB-USAGE.md` for workers and browser storage.

To extract all downloads through Docker, create a container from `vs69/tdlib:packages` with `--platform linux/amd64` and copy `/opt/tdlib/packages/.` to a local directory. Do not run that file container.

## Updates and verification

The publishing workflow runs automatically when build inputs change on `main` and checks official upstream `master` daily at **04:23 UTC (09:53 IST)**. It rebuilds when the upstream commit or build inputs change. No manual run is needed for routine updates; **Force rebuild** remains available for recovery. Unchanged publications skip compilation. Successful scheduled no-change checks are cleaned from Actions history; actual builds, failures and manual runs remain available.

Tags remain `latest`, `debian`, `alpine`, `dev`, `debian-dev`, `alpine-dev`, `android` and `packages`. No version-specific Docker tags are created. The GitHub release also uses `latest`. An upstream snapshot without an exact official tag is marked as a prerelease.

For repeatable deployments, pin an **image digest** and retain its manifest. For release downloads, obtain `SHA256SUMS` alongside the archives and run `sha256sum -c SHA256SUMS` in that directory. On macOS, use `shasum -a 256 -c SHA256SUMS`.

Publishing checks native JSON calls, Linux shared/static linking, Android ABI/JNI exports and alignment, portable package checksums, Apple architectures and WebAssembly startup. Cached outputs are verified before reuse. A completed release manifest is written only after all required images and downloads are published; interrupted publication is retried on the next check.

These checks validate packages, not every consuming application or Telegram login flow. Consult the [successful run](https://github.com/vigarepo2/TDLib/actions/workflows/build-and-publish.yml) and release manifest before adopting an update. Upstream can change its API without changing its version string.

## Publishing

Build pins are maintained in [`build.json`](https://github.com/vigarepo2/TDLib/blob/main/build.json). Production code is limited to native build recipes, package verification, publishing helpers and workflows.

1. Create the Docker Hub repository identified by `docker.image` in `build.json`.
2. Configure repository secrets `DOCKER_USER` and `DOCKER_PASSWORD`. Use a Docker Hub credential authorized to push images and update the repository description.
3. Run [Build and publish TDLib](https://github.com/vigarepo2/TDLib/actions/workflows/build-and-publish.yml). The workflow checks credentials before compilation and publishes Android as soon as its four ABI builds pass.

The **Validate** workflow checks configuration, script syntax and Docker targets without publishing credentials. Successful validation on `main` synchronizes this README and the short description to Docker Hub; documentation changes do not require a native rebuild.

Native builds run on Linux, Windows and macOS runners with their respective toolchains. To validate configuration locally, use Python 3.10+ and run `python3 scripts/check-upstream.py --validate`. Local native recipes require a clean official TDLib checkout and the pinned dependencies; the workflow contains the complete setup commands.

## License and security

Build scripts and documentation use the [Boost Software License 1.0](https://github.com/vigarepo2/TDLib/blob/main/LICENSE). Distributed dependencies retain their own licenses; see [third-party notices](https://github.com/vigarepo2/TDLib/blob/main/THIRD_PARTY_NOTICES.md) and the notices shipped in each package.

Report build or publication vulnerabilities through the [security policy](https://github.com/vigarepo2/TDLib/blob/main/SECURITY.md). Keep Telegram credentials, session databases and registry tokens out of source code, image layers and public logs.
