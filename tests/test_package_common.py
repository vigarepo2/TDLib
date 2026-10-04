"""Check portable provenance against a real Git checkout and file contents."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("package_common", Path(__file__).resolve().parents[1] / "scripts/package-common.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PortableManifestTests(unittest.TestCase):
    def test_provenance_and_license_checksums_are_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output = Path(temp) / "source", Path(temp) / "package"
            source.mkdir()
            output.mkdir()
            for path in ("LICENSE_1_0.txt", "sqlite/sqlite/LICENSE", "td/generate/tl-parser/LICENSE"):
                file = source / path
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("Fixture license\n")
            (source / "CMakeLists.txt").write_text("project(TDLib VERSION 1.8.67 LANGUAGES CXX C)\n")
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            subprocess.run(["git", "-C", str(source), "add", "."], check=True)
            subprocess.run(["git", "-C", str(source), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "Fixture"], check=True)
            library = output / "native.dll"
            library.write_bytes(b"fixture binary contents\x00")
            result = MODULE.manifest(source, output, "windows-x64", {"compiler": "fixture"})
            recorded = json.loads((output / "manifest.json").read_text())
            self.assertEqual(result, recorded)
            self.assertEqual(result["tdlib"]["version"], "1.8.67")
            self.assertEqual(len(result["tdlib"]["commit"]), 40)
            entries = {entry["path"]: entry for entry in result["files"]}
            self.assertEqual(entries["native.dll"]["sha256"], hashlib.sha256(library.read_bytes()).hexdigest())
            for name in ("TDLib-Boost-1.0.txt", "SQLCipher.txt", "tl-parser.txt"):
                self.assertIn("licenses/" + name, entries)
            self.assertNotIn("manifest.json", entries)
            self.assertIn("native.dll\n", (output / "SHA256SUMS").read_text())
            # Rerunning metadata must not recursively include its own prior output.
            self.assertEqual(MODULE.manifest(source, output, "windows-x64", {"compiler": "fixture"}), result)


if __name__ == "__main__":
    unittest.main()
