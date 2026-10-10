#!/usr/bin/env python3
"""Create and verify the reusable Android TDLib artifact image payload."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ABIS = ("arm64-v8a", "armeabi-v7a", "x86", "x86_64")
FORMAT = "org.vigarepo2.tdlib.android.v1"
LIBRARIES = ("libtdjson.so", "libtdjsonjava.so")
NATIVE_CONTRACT = {"interfaces": ["json", "json-java"], "cxx_runtime": "c++_static",
                   "openssl_linkage": "static", "optimization": "O2", "ndebug": True,
                   "lto": False, "page_size": 16384}
SOURCE_FILES = {
    "sources/JsonClient.java": "example/java/org/drinkless/tdlib/JsonClient.java",
    "sources/td_api.tl": "td/generate/scheme/td_api.tl",
    "licenses/TDLib.LICENSE_1_0.txt": "LICENSE_1_0.txt",
    "licenses/SQLCipher.LICENSE.txt": "sqlite/sqlite/LICENSE",
}
AUXILIARY = ("include/td/telegram/td_json_client.h", "include/td/telegram/td_log.h",
             "include/td/telegram/tdjson_export.h", "licenses/OpenSSL.LICENSE.txt",
             "licenses/Android-NDK.NOTICE.txt")
FILES = tuple(f"jniLibs/{abi}/{name}" for abi in ABIS for name in LIBRARIES) + tuple(SOURCE_FILES) + AUXILIARY
HEX256 = re.compile(r"[0-9a-f]{64}\Z")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_text(), object_pairs_hook=unique_object)


def regular(path, limit=256 * 1024 * 1024):
    if path.is_symlink() or not path.is_file() or any(p.is_symlink() for p in path.parents):
        raise ValueError(f"Not an ordinary file: {path}")
    if not 0 < path.stat().st_size <= limit:
        raise ValueError(f"Invalid file size: {path}")
    return path


def pins(config):
    value = read_json(config)["android"]
    if set(value["abis"]) != set(ABIS) or len(value["abis"]) != len(ABIS):
        raise ValueError("Android configuration must include all four ABIs")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value["ndk_version"]):
        raise ValueError("Invalid NDK version")
    if type(value["api"]) is not int or not 24 <= value["api"] <= 99:
        raise ValueError("Android API must be an integer of at least 24")
    ssl = value["openssl"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", ssl["version"]) or not HEX256.fullmatch(ssl["sha256"]):
        raise ValueError("Invalid OpenSSL pins")
    return value


def binding_hash(path):
    """Compare JNI declarations without app-specific static loading/error handlers."""
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", path.read_text(), flags=re.S)
    package = re.search(r"\bpackage\s+([\w.]+)\s*;", source)
    methods = re.findall(r"public\s+static\s+native\s+([^;]+);", source)
    callback = re.search(r"\bvoid\s+onLogMessage\s*\(([^)]*)\)\s*;", source)
    if not package or not methods or not callback:
        raise ValueError("Unrecognized JSONJava binding")
    normalize = lambda text: " ".join(text.split())
    contract = {"package": package.group(1), "methods": sorted(normalize(item) for item in methods),
                "log_callback": normalize(callback.group(1))}
    return hashlib.sha256(canonical(contract)).hexdigest()


def verify_library(path, abi, kind):
    regular(path)
    data = path.read_bytes()
    bits, machine = {"arm64-v8a": (2, 183), "armeabi-v7a": (1, 40),
                     "x86": (1, 3), "x86_64": (2, 62)}[abi]
    if (len(data) < 64 or data[:6] != b"\x7fELF" + bytes((bits, 1))
            or struct.unpack_from("<H", data, 18)[0] != machine
            or struct.unpack_from("<H", data, 16)[0] != 3):
        raise ValueError(f"Invalid Android ELF architecture/type: {abi}/{kind}")
    if bits == 2:
        phoff = struct.unpack_from("<Q", data, 32)[0]
        phsize, phcount = struct.unpack_from("<HH", data, 54)
        fmt, offset, address = "<IIQQQQQQ", 2, 3
    else:
        phoff = struct.unpack_from("<I", data, 28)[0]
        phsize, phcount = struct.unpack_from("<HH", data, 42)
        fmt, offset, address = "<IIIIIIII", 1, 2
    if phsize < struct.calcsize(fmt) or phoff + phsize * phcount > len(data):
        raise ValueError("Malformed ELF program headers")
    loads = 0
    for i in range(phcount):
        entry = struct.unpack_from(fmt, data, phoff + i * phsize)
        if entry[0] != 1:
            continue
        loads += 1
        if entry[7] < 16384 or entry[7] & (entry[7] - 1) or (entry[offset] - entry[address]) % 16384:
            raise ValueError("Android ELF lacks 16 KiB load alignment")
    if not loads:
        raise ValueError("ELF has no loadable segments")
    tool = shutil.which("readelf") or shutil.which("llvm-readelf")
    if not tool:
        raise ValueError("Install binutils: readelf is required")
    result = subprocess.run([tool, "--wide", "--dyn-syms", "--dynamic", str(path)],
                            text=True, capture_output=True, check=True, timeout=60).stdout
    required = (("JNI_OnLoad",) if kind == "libtdjsonjava.so" else
                ("td_create_client_id", "td_send", "td_receive", "td_execute"))
    for name in required:
        if not re.search(r"\bFUNC\s+GLOBAL\s+DEFAULT\s+(?!UND\b)\S+\s+" + name + r"\s*$", result, re.M):
            raise ValueError(f"Missing exported {name} in {abi}/{kind}")
    needed = set(re.findall(r"\(NEEDED\).*\[([^]]+)\]", result))
    if not needed <= {"libc.so", "libm.so", "libdl.so", "liblog.so", "libz.so", "libandroid.so"}:
        raise ValueError(f"Unexpected dynamic dependencies in Android library: {sorted(needed)}")


def source_identity(source):
    commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Invalid TDLib source commit")
    for command in (["diff", "--quiet"], ["diff", "--cached", "--quiet"]):
        subprocess.run(["git", "-C", str(source)] + command, check=True)
    version = re.search(r"project\(TDLib VERSION ([0-9]+\.[0-9]+\.[0-9]+)",
                        (source / "CMakeLists.txt").read_text())
    if not version:
        raise ValueError("Cannot identify official TDLib source version")
    return {"repository": "https://github.com/tdlib/td", "commit": commit, "version": version.group(1)}


def create(source, libraries, output, config, build_fingerprint):
    settings = pins(config)
    identity = source_identity(source)
    if not HEX256.fullmatch(build_fingerprint):
        raise ValueError("--build-fingerprint must be the checked build recipe SHA-256")
    if output.exists():
        raise ValueError("Output directory must not already exist")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".android-package-", dir=output.parent) as temporary:
        stage = Path(temporary) / "payload"
        for name in FILES:
            origin = source / SOURCE_FILES[name] if name in SOURCE_FILES else libraries.parent / name
            regular(origin, 256 * 1024 * 1024 if name.endswith(".so") else 8 * 1024 * 1024)
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, target)
            target.chmod(0o644)
        records = [{"path": name, "size": (stage / name).stat().st_size, "sha256": sha256(stage / name)} for name in FILES]
        manifest = {"schema": 1, "format": FORMAT, "platform": "android", "tdlib": identity,
                    "openssl": settings["openssl"], "ndk_version": settings["ndk_version"],
                    "android_api": settings["api"], "abis": list(ABIS),
                    "jni_binding_sha256": binding_hash(stage / "sources/JsonClient.java"),
                    "build_fingerprint": build_fingerprint, "native_contract": json.loads(canonical(NATIVE_CONTRACT)), "files": records}
        (stage / "manifest.json").write_bytes(canonical(manifest) + b"\n")
        names = ("manifest.json",) + FILES
        (stage / "checksums.sha256").write_text("".join(f"{sha256(stage / name)}  {name}\n" for name in names))
        verify(stage)
        stage.rename(output)
    return manifest


def verify(directory):
    manifest = read_json(regular(directory / "manifest.json", 128 * 1024))
    if (manifest.get("format") != FORMAT or manifest.get("schema") != 1
            or manifest.get("platform") != "android" or manifest.get("abis") != list(ABIS)):
        raise ValueError("Unsupported Android manifest")
    if canonical(manifest.get("native_contract")) != canonical(NATIVE_CONTRACT):
        raise ValueError("Unsupported Android native build contract")
    records = manifest.get("files")
    if not isinstance(records, list) or [r.get("path") for r in records] != list(FILES):
        raise ValueError("Manifest must describe complete exact Android payload")
    expected_files = set(FILES) | {"manifest.json", "checksums.sha256"}
    actual = set()
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlinks are not allowed in Android payload")
        if path.is_file():
            actual.add(path.relative_to(directory).as_posix())
        elif not path.is_dir():
            raise ValueError("Android payload contains a special file")
    if actual != expected_files:
        raise ValueError("Android payload contains missing or extra files")
    for record in records:
        path = regular(directory / record["path"], 256 * 1024 * 1024 if record["path"].endswith(".so") else 8 * 1024 * 1024)
        if record != {"path": record["path"], "size": path.stat().st_size, "sha256": sha256(path)}:
            raise ValueError(f"Android payload checksum or size mismatch: {record['path']}")
    expected_checksums = "".join(f"{sha256(directory / name)}  {name}\n" for name in ("manifest.json",) + FILES)
    if regular(directory / "checksums.sha256", 128 * 1024).read_text() != expected_checksums:
        raise ValueError("Android checksums file mismatch")
    if manifest["jni_binding_sha256"] != binding_hash(directory / "sources/JsonClient.java"):
        raise ValueError("JSONJava binding hash mismatch")
    for abi in ABIS:
        for name in LIBRARIES:
            verify_library(directory / f"jniLibs/{abi}/{name}", abi, name)
    return manifest


def zip_entry(archive, name, data):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data)


def aar(payload, output):
    """An optional conventional Android library for the official JSONJava API."""
    manifest = verify(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".android-aar-", dir=output.parent) as temporary:
        temporary = Path(temporary)
        classes = temporary / "classes"
        classes.mkdir()
        subprocess.run(["javac", "--release", "8", "-encoding", "UTF-8", "-d", str(classes),
                        str(payload / "sources/JsonClient.java")], check=True, timeout=60)
        classes_jar = temporary / "classes.jar"
        with zipfile.ZipFile(classes_jar, "w") as archive:
            for path in sorted(classes.rglob("*.class")):
                zip_entry(archive, path.relative_to(classes).as_posix(), path.read_bytes())
        staged = temporary / "tdlib.aar"
        with zipfile.ZipFile(staged, "w") as archive:
            android_manifest = ('<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
                                'package="org.drinkless.tdlib"><uses-sdk android:minSdkVersion="'
                                + str(manifest["android_api"]) + '" /></manifest>\n')
            zip_entry(archive, "AndroidManifest.xml", android_manifest.encode())
            zip_entry(archive, "classes.jar", classes_jar.read_bytes())
            zip_entry(archive, "R.txt", b"")
            zip_entry(archive, "proguard.txt", b"-keep class org.drinkless.tdlib.JsonClient { *; }\n"
                      b"-keep class org.drinkless.tdlib.JsonClient$LogMessageHandler { *; }\n")
            for abi in ABIS:
                zip_entry(archive, f"jni/{abi}/libtdjsonjava.so",
                          (payload / f"jniLibs/{abi}/libtdjsonjava.so").read_bytes())
            for path in sorted((payload / "licenses").iterdir()):
                zip_entry(archive, "assets/tdlib/licenses/" + path.name, path.read_bytes())
            zip_entry(archive, "assets/tdlib/manifest.json", (payload / "manifest.json").read_bytes())
        os.replace(staged, output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    item = commands.add_parser("pins")
    item.add_argument("--config", type=Path, default=ROOT / "build.json")
    item = commands.add_parser("create")
    item.add_argument("--source", type=Path, required=True)
    item.add_argument("--libraries", type=Path, required=True, help="Merged build output jniLibs directory")
    item.add_argument("--output", type=Path, required=True)
    item.add_argument("--config", type=Path, default=ROOT / "build.json")
    item.add_argument("--build-fingerprint", required=True)
    item = commands.add_parser("verify")
    item.add_argument("directory", type=Path)
    item = commands.add_parser("aar")
    item.add_argument("--payload", type=Path, required=True)
    item.add_argument("--output", type=Path, required=True)
    item = commands.add_parser("verify-library")
    item.add_argument("--abi", choices=ABIS, required=True)
    item.add_argument("--kind", choices=LIBRARIES, required=True)
    item.add_argument("library", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "pins":
            values = pins(args.config)
            print(values["ndk_version"], values["api"], values["openssl"]["version"], values["openssl"]["sha256"], sep="\n")
        elif args.command == "create":
            value = create(args.source, args.libraries, args.output, args.config, args.build_fingerprint)
            print(f"Packaged Android TDLib {value['tdlib']['version']} ({value['tdlib']['commit']})")
        elif args.command == "verify":
            verify(args.directory)
            print("Verified Android payload: all ABIs, checksums, JSON/JNI exports and 16 KiB alignment")
        elif args.command == "aar":
            aar(args.payload, args.output)
            print("Created Android JSONJava AAR (four ABIs, Java 8 classes, min SDK 24+)")
        else:
            verify_library(args.library, args.abi, args.kind)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Android package error: {error}\n")


if __name__ == "__main__":
    main()
