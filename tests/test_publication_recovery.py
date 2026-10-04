"""Publication can fail at any network operation; only its last step marks success."""
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("publish_release", ROOT / "scripts/publish-release.py")
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)


class PublicationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.collected = self.root / "collected"
        self.collected.mkdir()
        self.events = []
        self.digest = "sha256:" + "d" * 64
        self.write("upstream-check/check-result.json", json.dumps({"changed": True, "head_sha": "f" * 40, "run_id": "42", "upstream": {"commit": "a" * 40, "version": "1.8.67", "repository": "tdlib/td", "official_tag": None}, "build_fingerprint": "b" * 64}))
        for variant in ("debian", "alpine"):
            for arch in ("amd64", "arm64"):
                self.write(f"digests-linux-{variant}-{arch}/digests.json", json.dumps({"runtime": self.digest, "devel": self.digest}))
        for target in ("android", "packages"):
            self.write(f"digest-{target}/digest.txt", self.digest)
        for filename in ("tdlib-android.tar.gz", "tdlib-android.aar", "tdlib-windows-x64.tar.gz", "tdlib-apple.tar.gz", "tdlib-web.tar.gz"):
            self.write("package-fixture/" + filename, "compiled package fixture")
        events = self.events

        class API:
            repository = "vigarepo2/TDLib"

            def request(self, path, method="GET", body=None):
                events.append(("api", method, path))
                if method == "GET":
                    return {"id": 11, "assets": [{"name": "manifest.json", "id": 17}]}
                return {}

        self.api = API

    def write(self, name, text):
        target = self.collected / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def command(self, *args):
        self.events.append(("command", *args))
        if "inspect" in args:
            return json.dumps({"digest": self.digest})
        return ""

    def invoke(self, command=None):
        with mock.patch.object(publish, "GitHub", self.api), mock.patch.object(publish, "run", command or self.command), mock.patch.dict(os.environ, {"GITHUB_SHA": "f" * 40, "GITHUB_RUN_ID": "42"}), mock.patch.object(sys, "argv", ["publish-release.py", "--artifacts", str(self.collected), "--release", str(self.root / "release")]), mock.patch("builtins.print"):
            publish.main()

    def test_success_marker_is_uploaded_only_after_all_tags_and_payloads(self):
        self.invoke()
        deletes = [index for index, event in enumerate(self.events) if event[:2] == ("api", "DELETE")]
        creates = [index for index, event in enumerate(self.events) if event[:5] == ("command", "docker", "buildx", "imagetools", "create")]
        self.assertEqual(len(deletes), 1)
        self.assertEqual(len(creates), 8)
        self.assertLess(deletes[0], min(creates))
        self.assertEqual(self.events[-1][:4], ("command", "gh", "release", "upload"))
        self.assertTrue(self.events[-1][-1].endswith("/manifest.json"))
        self.assertFalse(any("manifest.json" in part for part in self.events[-2] if isinstance(part, str)))

    def test_failed_tag_promotion_cannot_leave_a_success_marker(self):
        def failing(*args):
            if "create" in args:
                self.events.append(("failed-promotion",))
                raise RuntimeError("registry unavailable")
            return self.command(*args)
        with self.assertRaisesRegex(RuntimeError, "registry unavailable"):
            self.invoke(failing)
        self.assertTrue(any(event[:2] == ("api", "DELETE") for event in self.events))
        self.assertFalse(any(event[:4] == ("command", "gh", "release", "upload") for event in self.events))

    def test_missing_platform_payload_prevents_any_publication(self):
        (self.collected / "package-fixture/tdlib-android.aar").unlink()
        with self.assertRaisesRegex(ValueError, "Expected exactly one tdlib-android.aar"):
            self.invoke()
        self.assertEqual(self.events, [])


if __name__ == "__main__":
    unittest.main()
