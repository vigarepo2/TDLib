# TDLib, ready for your next build

**Reusable Telegram libraries for apps, bots, and services. Built from upstream TDLib; distributed through Docker Hub and GitHub.**

[![Build and publish](https://github.com/vigarepo2/TDLib/actions/workflows/build-and-publish.yml/badge.svg)](https://github.com/vigarepo2/TDLib/actions/workflows/build-and-publish.yml)
[![License: BSL-1.0](https://img.shields.io/badge/license-BSL--1.0-blue)](https://github.com/vigarepo2/TDLib/blob/main/LICENSE)

[Docker Hub](https://hub.docker.com/r/vs69/tdlib) · [Download packages](https://github.com/vigarepo2/TDLib/releases/tag/latest) · [Quick start](https://github.com/vigarepo2/TDLib/blob/main/docs/QUICKSTART.md) · [Platform guide](https://github.com/vigarepo2/TDLib/blob/main/docs/platforms.md) · [Actions](https://github.com/vigarepo2/TDLib/actions)

TDLib is Telegram's library for networking, encryption, local storage, and updates. This project compiles it into reusable packages so your application does not have to rebuild the native engine every time you change its interface or business logic.

Think of these packages as the engine your application uses. They do not include a Telegram interface, bot implementation, HTTP API, or streaming server. Those features belong in the application built on top of TDLib.

This is an independent distribution maintained by [vigarepo2](https://github.com/vigarepo2), not an official Telegram publication. Packages record the exact upstream version and commit. A platform becomes available after its build and checks succeed; consult the latest successful publishing run and release manifest for what has actually been published.

## Choose your package

All images use the public repository **`vs69/tdlib`**. The word after the colon selects a package, not a TDLib version.

| Image | Intended use | Targets | Main contents |
| --- | --- | --- | --- |
| `vs69/tdlib:latest` or `:debian` | Run an application in Debian Linux | Linux amd64, arm64 | JSON shared library and runtime dependencies |
| `vs69/tdlib:alpine` | Run an application in Alpine Linux | Linux amd64, arm64 | JSON shared library and musl-compatible dependencies |
| `vs69/tdlib:dev` or `:debian-dev` | Compile code against TDLib on Debian | Linux amd64, arm64 | Runtime, headers, static libraries, CMake package, build tools |
| `vs69/tdlib:alpine-dev` | Compile code against TDLib on Alpine | Linux amd64, arm64 | Runtime, headers, static libraries, CMake package, build tools |
| `vs69/tdlib:android` | Supply native libraries to an Android app build | arm64-v8a, armeabi-v7a, x86, x86_64 | Android JSON/JNI libraries, Java source, headers, manifests |
| `vs69/tdlib:packages` | Extract packages for other platforms | Windows x64; macOS/iOS; browser | Platform archives and checksums |

The Android and packages images are **file containers**: create a container and copy its files out. They do not run an application. Windows, Apple, browser, and Android downloads are also available directly from the [rolling GitHub release](https://github.com/vigarepo2/TDLib/releases/tag/latest); Docker is optional for those downloads.

One project can provide these different packages. One native library cannot run on every operating system or CPU. A Linux image running in Docker Desktop on Windows or macOS still contains Linux libraries.

## Try the Linux image

Install Docker, then run:

```sh
docker pull vs69/tdlib:latest
docker run --rm vs69/tdlib:latest
```

The second command prints TDLib's version, commit, and a small text-processing check, then exits. It requires no Telegram account or bot token and does not start a server.

The runtime library is installed at `/usr/local/lib/libtdjson.so`. The image runs as the non-root `tdlib` user and provides `/data` as a writable working directory.

Use the image as a base for your own service, or copy the library into a compatible Linux image. The [language examples](https://github.com/vigarepo2/TDLib/tree/main/examples) show how to connect an application. The development variants include `/usr/local/include` and the installed CMake package for consumers that compile native code.

### Linux compatibility

The Debian build uses **Debian 12/bookworm, glibc 2.36**. The Alpine build uses **Alpine 3.23 and musl**. Both use the GCC C++ runtime, OpenSSL 3, and zlib. Debian and Alpine libraries are not interchangeable.

Keeping the supplied runtime image as your application's base is the simplest way to keep its dependencies aligned. When copying libraries into another image or onto a host, match CPU architecture, libc, required symbol versions, OpenSSL, zlib, and the C++ runtime. The word “Linux” alone is not enough to establish compatibility.

## Use the Android package

The Android package contains all four ABIs, built for **Android API 24+**, **NDK 28.2.13676358**, **OpenSSL 3.5.9**, and **16 KB native page alignment**. It includes both the JSON C interface and the JSON Java/JNI adapter.

```sh
docker pull --platform linux/amd64 vs69/tdlib:android
docker create --platform linux/amd64 --name tdlib-android vs69/tdlib:android
mkdir -p tdlib-android
docker cp tdlib-android:/opt/tdlib/android/. ./tdlib-android/
docker rm tdlib-android
```

`--platform linux/amd64` selects the file container even on an ARM computer. The container is never executed, so no CPU emulation is needed; it still contains Android libraries for all four ABIs.

For a Java/Kotlin application, use `sources/JsonClient.java` and the matching `jniLibs/<ABI>/libtdjsonjava.so` files. Applications using the C interface use `libtdjson.so` and the supplied headers. Keep bindings and native libraries from the same package. See the [Android integration guide](https://github.com/vigarepo2/TDLib/blob/main/docs/android.md) for the complete layout and integration details.

For a simpler Gradle integration, download `tdlib-android.aar` from the release, place it in `app/libs`, and add `implementation(files("libs/tdlib-android.aar"))` to the app's Kotlin Gradle dependencies. The AAR already contains the JSON Java adapter and all four JNI libraries; do not also copy those files into the same app. This adapter exchanges JSON strings and does not provide the separate generated `TdApi` Java class API.

### TelePlay

[TelePlay](https://github.com/vigarepo2/TelePlay) can reuse this public Android image when its source commit, toolchain, API level, schema, binding, and native checksums match the app's expected engine. It does not need Docker Hub credentials to pull a public image, subject to Docker Hub's public pull limits.

If the image is not available or its newest engine differs from TelePlay's pinned engine, TelePlay uses its existing verified native package or source build. This protects an app from silently combining a new native library with old bindings. Compatible application-only changes reuse the engine; an actual engine update still requires a native build and app compatibility checks.

## Other platforms and languages

The [platform guide](https://github.com/vigarepo2/TDLib/blob/main/docs/platforms.md) covers Windows DLLs, Apple frameworks, and browser WebAssembly. These packages have separate build recipes and checks.

| Language or application | Integration route |
| --- | --- |
| Python, Node.js, Ruby, PHP, Rust, Go, .NET, and other languages with native-library support | Use the JSON C interface through a compatible binding or foreign-function interface |
| C/C++ | Use the JSON interface and headers; development images also contain the installed static libraries and CMake configuration |
| Android Java/Kotlin | Use the packaged JSON Java/JNI adapter and Android libraries |
| Native Windows applications | Use the Windows package; match your language adapter to its JSON interface |
| macOS/iOS applications | Use the Apple libraries or XCFramework with an application-side adapter |
| Browser applications | Use the `tdweb` package and its WebAssembly assets |

A language binding is the adapter between your language and TDLib. The presence of a JSON interface does not mean every third-party adapter or framework version has been tested by this project. The package does not turn native TDLib into a browser library; use the dedicated web build there.

## Updates without a pile of version tags

The **Build and publish TDLib** workflow checks the official [`tdlib/td` source](https://github.com/tdlib/td) daily. It compares the upstream commit and this project's build inputs with the last published manifest.

- **No relevant change:** compilation and publishing are skipped.
- **New source or changed build inputs:** the target packages are rebuilt and checked before their rolling packages are published.
- **Manual rebuild:** maintainers can select **Force rebuild** when a rebuild is needed with the same recorded inputs.

The public tags stay simple: `latest`, `debian`, `alpine`, `dev`, `debian-dev`, `alpine-dev`, `android`, and `packages`. No per-version Docker tags are created. The single GitHub release is also named `latest`; its title and manifest identify the upstream version and full source commit used for that build. Release notes identify a matching upstream tag when present; other upstream snapshots are marked as prereleases.

TDLib can change its source without changing its version number. For that reason, a commit and build fingerprint are recorded as well as the version. Tracking upstream `master` is not the same as waiting for an official stable release announcement.

For repeatable deployments, record the resolved image digest and the manifest with your application build. A rolling tag can move. Replacing a tag also does not guarantee that Docker Hub immediately removes all unreferenced storage; registry retention is controlled by Docker Hub.

Successful scheduled checks that find no change are removed from the Actions history after they finish. Failed checks, builds, and manual runs remain for troubleshooting. The cleanup workflow maintains its own small history; a completed no-change check can appear briefly before cleanup runs. [Maintenance details](https://github.com/vigarepo2/TDLib/blob/main/docs/MAINTAINERS.md)

## What is checked

Builds verify the selected upstream source, package structure, and checksums. Linux images load the actual shared library and execute harmless JSON calls. Android packages are checked for all four ABIs, exported interfaces, required files, matching bindings, and 16 KB ELF alignment. Windows/macOS smoke checks load their native library, and the web check loads WebAssembly.

These are build and library checks. They do not log into Telegram, test an application on every device, or guarantee that a future upstream change will compile without maintenance. Check the run results before relying on a new package.

Archives include license notices and machine-readable metadata. The rolling release publishes `manifest.json` and `SHA256SUMS`; Linux images also include `/usr/local/share/tdlib/build.json` and OCI labels with their source details.

## Set up your own publication

For this repository, the destination is **[Docker Hub: vs69/tdlib](https://hub.docker.com/r/vs69/tdlib)**.

1. Create the public `tdlib` repository in the `vs69` Docker Hub account.
2. Add GitHub Actions secrets **`DOCKER_USER`** (`vs69`) and **`DOCKER_PASSWORD`** (your Docker Hub account password).
3. Run **Build and publish TDLib** once from the Actions tab.

The [quick start](https://github.com/vigarepo2/TDLib/blob/main/docs/QUICKSTART.md) explains the exact screens, login setup, workflow choices, and first-build expectations. Publishing and successful `main` validation runs update the Docker Hub overview from this README when configured, so documentation changes do not need a new native build.

Prebuilt packages remove repeated native compilation from consumer builds. Image downloads, unpacking, application compilation, signing, and upload still take time. There is no fixed APK-build time guarantee; measure your own workflow after the first successful engine publication.

## License and upstream

Build scripts and documentation use the [Boost Software License 1.0](https://github.com/vigarepo2/TDLib/blob/main/LICENSE). Included software retains its own licenses; see [third-party notices](https://github.com/vigarepo2/TDLib/blob/main/THIRD_PARTY_NOTICES.md).

[Official TDLib documentation](https://core.telegram.org/tdlib) · [Official source](https://github.com/tdlib/td) · [Contributing](https://github.com/vigarepo2/TDLib/blob/main/CONTRIBUTING.md) · [Security](https://github.com/vigarepo2/TDLib/blob/main/SECURITY.md)
