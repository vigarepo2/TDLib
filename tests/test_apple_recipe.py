"""Exercise the Apple recipe's architecture checks with real Mach-O fixtures."""
import os
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LIPO = os.environ.get("LIPO") or shutil.which("lipo") or shutil.which("llvm-lipo")


class AppleRecipeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.commands = [
            shlex.split(line)
            for line in (ROOT / "scripts/build-apple.sh").read_text().splitlines()
            if line.startswith("lipo ") and "-verify_arch" in line
        ]

    def test_each_platform_keeps_input_before_variadic_architecture_argument(self):
        self.assertEqual(3, len(self.commands))
        checked = {}
        for command in self.commands:
            self.assertEqual("-verify_arch", command[2],
                             "Apple lipo treats all remaining arguments as architectures")
            checked[command[1]] = command[3:]
        self.assertEqual({
            "$OUTPUT/macos/lib/libtdjson.dylib": ["arm64", "x86_64"],
            "$OUTPUT/ios/lib/libtdjson.dylib": ["arm64"],
            "$OUTPUT/ios-simulator/lib/libtdjson.dylib": ["arm64", "x86_64"],
        }, checked)

    @unittest.skipUnless(LIPO, "Apple lipo or LLVM llvm-lipo is required")
    def test_real_lipo_accepts_complete_slices_and_rejects_missing_architectures(self):
        with tempfile.TemporaryDirectory(prefix="tdlib apple ") as directory:
            output = Path(directory)
            objects = {}
            # Minimal valid MH_OBJECT Mach-O files suffice to test architecture
            # parsing without an Apple SDK or rebuilding any TDLib sources.
            for arch, cpu, subtype in (("arm64", 0x100000C, 0), ("x86_64", 0x1000007, 3)):
                path = output / (arch + ".o")
                path.write_bytes(struct.pack("<IiiIIIII", 0xFEEDFACF, cpu, subtype, 1, 0, 0, 0, 0))
                objects[arch] = path
            for command in self.commands:
                arguments = [LIPO] + [value.replace("$OUTPUT", str(output)) for value in command[1:]]
                path = Path(arguments[1])
                path.parent.mkdir(parents=True, exist_ok=True)
                arches = arguments[3:]
                subprocess.run([LIPO, "-create", *[str(objects[arch]) for arch in arches],
                                "-output", str(path)], check=True, capture_output=True, text=True)
                subprocess.run(arguments, check=True, capture_output=True, text=True)
                missing = "x86_64" if arches == ["arm64"] else "arm64"
                available = "arm64" if missing == "x86_64" else "x86_64"
                shutil.copyfile(objects[available], path)
                negative = arguments if len(arches) > 1 else arguments + [missing]
                result = subprocess.run(negative, capture_output=True, text=True)
                self.assertNotEqual(0, result.returncode, "Missing architectures must stop packaging")


if __name__ == "__main__":
    unittest.main()
