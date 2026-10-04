"""Android package integrity and JNI/AAR integration regressions."""
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tdlib_android_package", ROOT / "scripts/package-android.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)
JAVA = '''package org.drinkless.tdlib;
public final class JsonClient {
  public static native int createClientId();
  public static native void send(int clientId, String request);
  public static native String receive(double timeout);
  public static native String execute(String request);
  public interface LogMessageHandler { void onLogMessage(int verbosityLevel, String message); }
  public static native void setLogMessageHandler(int maxVerbosityLevel, JsonClient.LogMessageHandler logMessageHandler);
}
'''


def elf(abi):
    bits, machine = {"arm64-v8a": (2, 183), "armeabi-v7a": (1, 40), "x86": (1, 3), "x86_64": (2, 62)}[abi]
    data = bytearray(256)
    data[:6] = b"\x7fELF" + bytes((bits, 1))
    struct.pack_into("<HH", data, 16, 3, machine)
    if bits == 2:
        struct.pack_into("<Q", data, 32, 64)
        struct.pack_into("<HH", data, 54, 56, 1)
        struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, 0, 0, 0, 256, 256, 16384)
    else:
        struct.pack_into("<I", data, 28, 64)
        struct.pack_into("<HH", data, 42, 32, 1)
        struct.pack_into("<IIIIIIII", data, 64, 1, 0, 0, 0, 256, 256, 5, 16384)
    return bytes(data)


class AndroidPackageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.input = self.root / "build"
        self.output = self.root / "payload"
        for name in package.FILES:
            target = (self.source / package.SOURCE_FILES[name] if name in package.SOURCE_FILES else self.input / name)
            target.parent.mkdir(parents=True, exist_ok=True)
            if name.endswith(".so"):
                target.write_bytes(elf(name.split("/")[1]))
            elif name.endswith("JsonClient.java"):
                target.write_text(JAVA)
            else:
                target.write_text("public source/license fixture\n")
        self.actual_run = subprocess.run
        self.symbols = "\n".join(f"1: 000000001 12 FUNC GLOBAL DEFAULT 4 {name}" for name in
                                  ("JNI_OnLoad", "td_create_client_id", "td_send", "td_receive", "td_execute"))
        self.dynamic = " (NEEDED) Shared library: [libc.so]\n"
        source = mock.patch.object(package, "source_identity", return_value={
            "repository": "https://github.com/tdlib/td", "commit": "a" * 40, "version": "1.8.67"})
        source.start()
        self.addCleanup(source.stop)
        run = mock.patch.object(package.subprocess, "run", side_effect=self.command)
        run.start()
        self.addCleanup(run.stop)

    def command(self, command, **kwargs):
        if Path(command[0]).name in ("readelf", "llvm-readelf"):
            return subprocess.CompletedProcess(command, 0, self.symbols + "\n" + self.dynamic, "")
        return self.actual_run(command, **kwargs)

    def create(self):
        return package.create(self.source, self.input / "jniLibs", self.output, ROOT / "config/build.json", "b" * 64)

    def test_package_is_complete_verifiable_and_reproducible(self):
        manifest = self.create()
        self.assertEqual(8, len([row for row in manifest["files"] if row["path"].endswith(".so")]))
        self.assertEqual(list(package.ABIS), manifest["abis"])
        first = (self.output / "manifest.json").read_bytes()
        self.assertEqual(manifest, package.verify(self.output))
        shutil.rmtree(self.output)
        self.create()
        self.assertEqual(first, (self.output / "manifest.json").read_bytes())

    def test_tampered_bytes_and_checksum_document_are_rejected(self):
        self.create()
        checksums = self.output / "checksums.sha256"
        original = checksums.read_bytes()
        checksums.write_bytes(original + b"unexpected\n")
        with self.assertRaisesRegex(ValueError, "checksums file"):
            package.verify(self.output)
        checksums.write_bytes(original)
        library = self.output / package.FILES[0]
        library.write_bytes(library.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "checksum or size"):
            package.verify(self.output)

    def test_extra_file_and_symlink_are_rejected(self):
        self.create()
        extra = self.output / "secret.env"
        extra.write_text("no secrets")
        with self.assertRaisesRegex(ValueError, "missing or extra"):
            package.verify(self.output)
        extra.unlink()
        extra.symlink_to(self.output / "manifest.json")
        with self.assertRaisesRegex(ValueError, "Symlinks"):
            package.verify(self.output)

    def test_missing_architecture_cannot_be_packaged(self):
        (self.input / package.FILES[0]).unlink()
        with self.assertRaisesRegex(ValueError, "ordinary file"):
            self.create()
        self.assertFalse(self.output.exists())

    def test_wrong_elf_and_unaligned_libraries_are_rejected(self):
        path = self.input / package.FILES[0]
        for offset, value in ((18, 62), (112, 4096)):
            data = bytearray(elf("arm64-v8a"))
            struct.pack_into("<H" if offset == 18 else "<Q", data, offset, value)
            path.write_bytes(data)
            with self.assertRaises(ValueError):
                self.create()
            self.assertFalse(self.output.exists())

    def test_missing_exports_and_unexpected_dynamic_dependencies_fail(self):
        original = self.symbols
        self.symbols = self.symbols.replace("DEFAULT 4 td_send", "DEFAULT UND td_send")
        with self.assertRaisesRegex(ValueError, "Missing exported"):
            self.create()
        self.symbols = original
        self.dynamic += " (NEEDED) Shared library: [libcrypto.so]\n"
        with self.assertRaisesRegex(ValueError, "Unexpected dynamic dependencies"):
            self.create()

    def test_build_config_requires_all_abis_and_exact_checksum(self):
        config = json.loads((ROOT / "config/build.json").read_text())
        target = self.root / "config.json"
        config["android"]["abis"].pop()
        target.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, "all four"):
            package.pins(target)
        config["android"]["abis"] = list(package.ABIS)
        config["android"]["openssl"]["sha256"] = "unverified"
        target.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, "OpenSSL"):
            package.pins(target)

    @unittest.skipUnless(shutil.which("javac"), "JDK required for actual AAR compilation")
    def test_aar_compiles_official_json_bridge_and_preserves_four_jni_abis(self):
        self.create()
        target = self.root / "tdlib-android.aar"
        package.aar(self.output, target)
        with zipfile.ZipFile(target) as archive:
            names = set(archive.namelist())
            self.assertTrue({f"jni/{abi}/libtdjsonjava.so" for abi in package.ABIS} <= names)
            self.assertFalse(any(name.endswith("/libtdjson.so") for name in names))
            self.assertIn(b'minSdkVersion="24"', archive.read("AndroidManifest.xml"))
            self.assertIn(b"JsonClient$LogMessageHandler", archive.read("proguard.txt"))
            jar = self.root / "classes.jar"
            jar.write_bytes(archive.read("classes.jar"))
        with zipfile.ZipFile(jar) as archive:
            bytecode = archive.read("org/drinkless/tdlib/JsonClient.class")
            self.assertEqual(52, struct.unpack_from(">H", bytecode, 6)[0], "Java 8 bytecode must remain usable on Android API 24")


if __name__ == "__main__":
    unittest.main()
