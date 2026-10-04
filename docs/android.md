# Android integration

The Android package is compiled for API 24 and later, with NDK `28.2.13676358` and OpenSSL `3.5.9`. It contains these ABIs:

```text
arm64-v8a    armeabi-v7a    x86    x86_64
```

The native libraries are checked for 16 KB ELF alignment. Your app's Android Gradle Plugin and APK packaging must also handle 16 KB pages correctly; verify the finished APK on the Android versions and devices you support.

The `android` Docker tag is published as soon as the Android packaging job passes, independently of other platforms. TelePlay can use that image immediately. AAR and archive downloads in the rolling GitHub release are replaced after the complete all-platform publication succeeds; they can briefly contain an older engine while other targets are still building. Check the package manifest when choosing an input.

## Option A: use the AAR in Java or Kotlin

After a successful publication, download `tdlib-android.aar` from the [latest release](https://github.com/vigarepo2/TDLib/releases/tag/latest) and place it at `app/libs/tdlib-android.aar`.

Add this dependency in `app/build.gradle.kts`:

```kotlin
dependencies {
    implementation(files("libs/tdlib-android.aar"))
}
```

The AAR includes the upstream `org.drinkless.tdlib.JsonClient` class, the matching JNI libraries for all four ABIs, consumer R8 rules, and provenance/license assets. Set your app's minimum SDK to at least 24. Do not also add copies of the same Java class or native libraries under `app/src/main`; duplicate inputs can cause packaging conflicts.

You can check the JSON adapter without logging in:

```kotlin
import org.drinkless.tdlib.JsonClient

val version = JsonClient.execute("""{"@type":"getOption","name":"version"}""")
```

This package exposes TDLib's **JSON Java interface**. It does not include the generated typed `TdApi` classes used by a different TDLib Java interface. Choose an adapter compatible with the JSON interface when integrating other libraries.

## Option B: extract the native files

Use this option when you manage JNI files directly or need the JSON C interface. With Docker installed:

```sh
docker pull --platform linux/amd64 vs69/tdlib:android
docker create --platform linux/amd64 --name tdlib-android vs69/tdlib:android
mkdir -p tdlib-android
docker cp tdlib-android:/opt/tdlib/android/. ./tdlib-android/
docker rm tdlib-android
```

The image is a container of files with no runnable program. Use `docker create` and `docker cp`, not `docker run`. The explicit Linux amd64 platform selects this file container on any Docker host, including Apple Silicon; it does not restrict the Android ABIs inside it. Since nothing executes, no CPU emulation is needed.

Alternatively, download `tdlib-android.tar.gz` and its checksum from the [rolling release](https://github.com/vigarepo2/TDLib/releases/tag/latest). The archive contains the same Android package, without requiring Docker.

Its important paths are:

```text
manifest.json
checksums.sha256
jniLibs/
  arm64-v8a/   libtdjson.so, libtdjsonjava.so
  armeabi-v7a/ libtdjson.so, libtdjsonjava.so
  x86/         libtdjson.so, libtdjsonjava.so
  x86_64/      libtdjson.so, libtdjsonjava.so
include/td/telegram/
sources/JsonClient.java
sources/td_api.tl
licenses/
```

From a Linux shell, check the extracted files before copying them into your app:

```sh
(cd tdlib-android && sha256sum -c checksums.sha256)
```

On macOS, use `shasum -a 256 -c checksums.sha256` in that directory. These hashes detect changed files; obtain the manifest and package from the trusted publication linked above.

For Java/Kotlin integration without the AAR:

1. Copy `sources/JsonClient.java` to `app/src/main/java/org/drinkless/tdlib/JsonClient.java`.
2. Copy each `jniLibs/<ABI>/libtdjsonjava.so` to `app/src/main/jniLibs/<ABI>/libtdjsonjava.so`.
3. Preserve the JNI class and its native method names in release builds. If you maintain shrinker rules yourself, include:

   ```proguard
   -keep class org.drinkless.tdlib.JsonClient { *; }
   -keep class org.drinkless.tdlib.JsonClient$* { *; }
   ```

4. Keep the package manifest and license notices with your dependency records.

The JNI library is self-contained with respect to TDLib's JSON implementation; this Java integration does not also need `libtdjson.so`. C/FFI integrations use `libtdjson.so` and the headers instead. Including both libraries when only one interface is used increases APK size unnecessarily.

## Using the library in an application

Most TDLib calls are asynchronous. Create a client, send JSON requests, receive responses and updates on a dedicated receiver, and handle each authorization state. The upstream `JsonClient.receive` method must not be called concurrently from multiple threads. Do not block Android's UI thread waiting for updates.

Your app owns Telegram API credentials, login codes, two-step verification, session storage, media policy, and Android lifecycle/background behavior. None of those credentials belong in this distribution repository or its Docker image. Read the [TDLib getting-started documentation](https://core.telegram.org/tdlib/getting-started) before implementing authorization.

Use the `td_api.tl` shipped with your exact package as the API reference. Update Java source, schemas, and native files together; mixing versions can fail even if a shared library loads successfully.

## TelePlay's compatibility checks

TelePlay's build verifies the candidate package against its expected native engine and binding. Its APK workflows require the matching public image and never compile TDLib. If the image is unavailable or has moved to a different engine, TelePlay stops early and links to this repository's producer workflow. If a package claims to match but its files fail validation, the build fails instead of accepting the damaged files.

Updating `vs69/tdlib:android` therefore does not silently upgrade TelePlay. To adopt a new engine, update TelePlay's expected inputs and bindings together, then run its application checks. Once that combination is compatible, future application builds can reuse it.
