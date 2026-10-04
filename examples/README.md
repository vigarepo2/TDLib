# Run an offline TDLib query in your language

These examples load the **Linux JSON library** and print its TDLib version. They do not need a Telegram account, API credentials, or network connection when run. The sample code is intentionally small: login, updates, persistence, and error handling belong in your application.

Use a matching Linux image or install its libraries into a compatible Linux environment first. `debian` requires glibc; `alpine` requires musl. Native Windows, macOS, Android and browser applications cannot load these Linux `.so` files. On Windows/macOS, the Docker examples run **inside Linux containers**.

## Python — no pip packages

From the repository root:

```sh
docker build -f examples/python/Dockerfile -t tdlib-python .
docker run --rm tdlib-python
```

With TDLib already installed in your compatible Linux environment:

```sh
python3 examples/python/main.py
```

## Node.js — Koffi adapter

With Node.js and TDLib installed in a compatible Linux environment:

```sh
cd examples/node
npm ci
npm start
```

Koffi supplies the JavaScript-to-C adapter. This is a JSON API example, not a complete Telegram client package.

## Go — cgo

Go needs the `debian-dev` or `alpine-dev` headers at **build time**, a C compiler, and `CGO_ENABLED=1`. The compiled program needs the matching runtime library at run time.

```sh
docker build -f examples/go/Dockerfile -t tdlib-go .
docker run --rm tdlib-go
```

Or, with headers and libraries installed in a compatible Linux development environment:

```sh
cd examples/go
CGO_ENABLED=1 go run .
```

## Java or Kotlin/JVM — JNA adapter

With JDK 17+, Maven and the Linux runtime library installed:

```sh
cd examples/java
mvn compile exec:java
```

The example uses JNA to call the JSON C interface. Kotlin/JVM can use the same JNA interface. The Linux runtime images **do not** ship TDLib's typed `Client.java`/`TdApi.java` JNI bindings. Android uses the separate `android` package described in the main documentation.

## C# / .NET — P/Invoke

With .NET 8+ and the Linux runtime library installed:

```sh
dotnet run --project examples/csharp
```

`DllImport` loads `libtdjson.so` through the Linux library search path. If installed outside a system path, set `LD_LIBRARY_PATH` to the directory containing that file.

## C++ — CMake package

In a Linux development image with this repository mounted:

```sh
docker run --rm --user "$(id -u):$(id -g)" \
  -v "$PWD:/work" -w /work vs69/tdlib:debian-dev \
  sh -c 'cmake -S examples/cpp -B /tmp/tdlib-example && cmake --build /tmp/tdlib-example && /tmp/tdlib-example/tdlib-cpp'
```

The example links `Td::TdJson` dynamically. Development images also include the upstream static libraries and `Td::TdJsonStatic`/`Td::TdStatic` CMake targets. Static linkage still needs the target system's OpenSSL, zlib, thread and other required system libraries; it does not create a portable all-platform binary.

## Next: build your application

`td_execute` handles only methods documented as synchronous. Normal Telegram operations use `td_create_client_id`, `td_send`, and `td_receive`, following [TDLib's JSON interface documentation](https://core.telegram.org/tdlib/docs/td__json__client_8h.html). Use a single receive loop and process updates in order. Supply your own API ID/hash and handle authorization states, including two-step verification.

Do not put account sessions, tokens, passwords or API secrets into an image. Keep session data in an application-owned writable directory or volume. These images expose no HTTP API and have no default Telegram login.

CI exercises the native JSON library for each supported Linux architecture and libc variant. Development images also compile and execute the C++ example with both shared and static TDLib linkage. The other language examples explain adapters; they do not claim end-to-end Telegram client verification.
