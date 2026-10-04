# Native Windows, Apple and browser packages

The `vs69/tdlib:packages` image is a delivery box, **not a Windows, Apple or browser runtime**. It contains platform archives under `/opt/tdlib/packages`. The same archives are attached to this repository's single rolling GitHub release. Docker itself does not run an iOS app or turn a Linux `.so` into a Windows `.dll`.

Each package includes `manifest.json` with the exact official TDLib version and commit, compiler details, per-file SHA-256 checksums, `td_api.tl`, and license notices. Check the successful publishing workflow and package manifest for the artifacts actually available. A recipe in this repository is not a claim that every application or device has been tested.

Download and extract the delivery image without starting it:

```bash
docker pull --platform linux/amd64 vs69/tdlib:packages
docker create --platform linux/amd64 --name tdlib-packages vs69/tdlib:packages
mkdir -p tdlib-packages
docker cp tdlib-packages:/opt/tdlib/packages/. ./tdlib-packages/
docker rm tdlib-packages
```

The image manifest uses `linux/amd64` because this is a box of files. Copying those files does not execute Linux code or require CPU emulation, including on ARM64 Docker hosts. Unpack the archive for your target platform before following the examples below. If Docker is not installed, download the same archive from the [rolling release](https://github.com/vigarepo2/TDLib/releases/tag/rolling).

## Windows x64

The `windows-x64` package contains `bin/tdjson.dll`, C headers under `include/td/telegram`, and the linker import library under `lib`. OpenSSL and zlib are statically linked. Install Microsoft's [Visual C++ x64 Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist) on the consuming machine. ARM64 and 32-bit Windows are not included.

Python requires no Telegram login to check that the library loads:

```python
import ctypes
import json
from pathlib import Path

library = ctypes.CDLL(str(Path("windows-x64/bin/tdjson.dll").resolve()))
library.td_execute.argtypes = [ctypes.c_char_p]
library.td_execute.restype = ctypes.c_char_p
print(json.loads(library.td_execute(
    b'{"@type":"getTextEntities","text":"https://telegram.org"}'
)))
```

C#, Rust, Node and other languages must use a compatible JSON-API binding/FFI adapter. This package is the native C JSON ABI; it is not a generated .NET assembly or Java JNI binding.

To build: PowerShell 7 on Windows x64 with Visual Studio 2022 C++ tools, CMake, Git and Python installed:

```powershell
pwsh scripts/build-windows.ps1 -Source upstream
```

The recipe bootstraps the exact official vcpkg release commit pinned in `config/build.json`, installs its pinned OpenSSL/zlib/gperf ports, builds Release, loads the produced DLL and executes the text-entity JSON API. vcpkg port versions are recorded in the manifest; these Windows dependencies may differ from the OpenSSL version used by Android/Apple/WebAssembly.

## macOS and iOS

The `apple` package contains:

| Path | Platform |
| --- | --- |
| `TDLib.xcframework` | Combined Xcode package containing the three platform variants below |
| `macos/lib/libtdjson.dylib` | macOS 11+, ARM64 and x86_64 |
| `ios/lib/libtdjson.dylib` | iOS 13+, ARM64 devices |
| `ios-simulator/lib/libtdjson.dylib` | iOS 13+ simulator, ARM64 and x86_64 |
| `include/td/telegram` | C JSON API headers |

OpenSSL is linked into each library. macOS/iOS system libraries such as libc++, libSystem and zlib remain system dependencies. The minimum OS versions and architectures are recorded in the manifest. No watchOS, tvOS, visionOS or Catalyst slices are included.

Add the appropriate native library or XCFramework to your Xcode project, expose the C headers to your language, and configure your app's runtime search paths and signing. The XCFramework carries dylibs, following TDLib's official Apple packaging example; it is not a pre-signed application or a Swift Package. Your application must handle embedding/signing according to its platform and distribution requirements. Simulator and device libraries cannot be interchanged.

The macOS JSON API can also be used with Python's `ctypes.CDLL` exactly like the Windows example, changing the path to `apple/macos/lib/libtdjson.dylib`.

To build on macOS with full Xcode and its iOS SDK installed:

```bash
brew install cmake ninja gperf
bash scripts/build-apple.sh --source upstream
```

The first build compiles five slices and can take considerably longer than one Linux/Android ABI. CI checks all output architectures and loads the actual macOS library to execute its JSON API. iOS device login, application integration and App Store acceptance require testing in the consuming app; they are not covered by the package smoke test.

## Browser WebAssembly

The `web` package includes the official `tdweb-<version>.tgz` npm package, its `dist` folder, raw `wasm/td_wasm.js` and `wasm/td_wasm.wasm`, the official wrapper's usage guide and exact npm lock file. Install the local archive:

```bash
npm install ./web/tdweb-*.tgz
```

Host **all** files from `node_modules/tdweb/dist/` together in your web server's public directory. The wrapper loads worker scripts, JavaScript chunks and a `.wasm` file; copying only `tdweb.js` is insufficient. Use HTTPS in production and serve `.wasm` with `Content-Type: application/wasm`. Browser storage restrictions, Content Security Policy, Web Workers and your bundler affect application integration.

The official wrapper supports asynchronous requests and updates. For example, after loading the UMD script from your public directory:

```html
<script src="./tdweb.js"></script>
<script>
  const TdClient = tdweb.default;
  const client = new TdClient({
    instanceName: 'my-telegram-client',
    onUpdate: update => console.log(update)
  });
  client.send({ '@type': 'getTextEntities', text: 'https://telegram.org' })
    .then(console.log);
</script>
```

Real Telegram access still requires your own Telegram API ID/hash, the authorization flow and proper handling of updates. Browser network and storage capabilities differ from the native JSON client. Read the bundled `TDWEB-USAGE.md` and the [official wrapper source](https://github.com/tdlib/td/tree/master/example/web/tdweb) before integrating.

To build on Linux, install the native TDLib build tools, Node 22/npm and activate **Emscripten 3.1.1** as pinned by the official TDLib browser example, then:

```bash
bash scripts/build-web.sh --source upstream
```

This recipe replaces the example's obsolete OpenSSL 1.1.0 download with our checksummed OpenSSL LTS source. It keeps the exact upstream npm lock and wrapper. Upstream currently uses older JavaScript tooling; the build enables Node's legacy provider only for webpack 4 packaging. Publishing does not claim those upstream dependencies have been audited or modernized. The smoke test instantiates the built WebAssembly and executes the JSON API under Node; it does not claim a full browser Telegram login test.

## What stays the same across languages

TDLib's JSON message format is shared. Your platform's native file, language adapter, packaging and authorization handling are not. Use the exact `td_api.tl` delivered with a package to understand its API. An update may add or change methods; test your adapter and application before replacing a known working library.
