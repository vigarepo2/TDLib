# Third-party notices

This repository packages software from the projects below. Their authors retain their copyrights. The repository's Boost Software License applies to this project's build scripts and documentation; it does not replace the licenses of dependencies or container base images.

| Component | Upstream source | License |
| --- | --- | --- |
| TDLib | [tdlib/td](https://github.com/tdlib/td) | [Boost Software License 1.0](https://github.com/tdlib/td/blob/master/LICENSE_1_0.txt) |
| OpenSSL 3 | [openssl/openssl](https://github.com/openssl/openssl) | [Apache License 2.0](https://github.com/openssl/openssl/blob/master/LICENSE.txt) |
| zlib | [madler/zlib](https://github.com/madler/zlib) | [zlib license](https://github.com/madler/zlib/blob/develop/LICENSE) |
| SQLCipher code distributed with TDLib | [tdlib/td third-party code](https://github.com/tdlib/td/tree/master/td/sqlite) | License supplied with the bundled SQLCipher source |
| Android NDK runtime components | [Android NDK](https://developer.android.com/ndk) | Applicable notices included in the NDK distribution |
| Emscripten runtime | [emscripten-core/emscripten](https://github.com/emscripten-core/emscripten) | [MIT / University of Illinois-NCSA licenses](https://github.com/emscripten-core/emscripten/blob/main/LICENSE) |

Native package archives contain the applicable license files copied from the inputs used for that build. Linux images also carry distribution notices under `/usr/local/share/tdlib/`; operating-system packages retain their own notices in the base image. Consult the archive or image you distribute for the actual dependency notices, because the set of components differs by target.

Debian, Alpine Linux, compiler runtimes, Windows dependencies, npm dependencies, and Apple SDK components have separate terms. Installing a development image or redistributing a derived application does not change those terms.

TDLib and Telegram are upstream projects. This distribution is independently maintained by [vigarepo2](https://github.com/vigarepo2) and is not an official Telegram publication or endorsement.
