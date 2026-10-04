"""Android can be published early without marking incomplete releases successful."""
import importlib.util
import json
import os
import pathlib
import sys
import unittest
import urllib.error
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("publish_android", ROOT / "scripts/publish-android.py")
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)


class AndroidPublicationTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.digest = "sha256:" + "d" * 64
        self.check = {"changed": True, "repository": "vigarepo2/TDLib", "head_sha": "f" * 40, "run_id": "42", "upstream": {"commit": "a" * 40}, "build_fingerprint": "b" * 64}
        self.payload = {"tdlib": {"commit": "a" * 40}, "build_fingerprint": "b" * 64}
        events = self.events

        class API:
            repository = "vigarepo2/TDLib"

            def request(self, path, method="GET", body=None):
                events.append(("api", method, path))
                if method == "GET":
                    return {"assets": [{"name": "manifest.json", "id": 17}]}
                return {}

        self.api = API()

    def command(self, *arguments):
        self.events.append(("command", *arguments))
        return json.dumps({"digest": self.digest}) if "inspect" in arguments else ""

    def invoke(self, command=None):
        with mock.patch.object(publish, "run", command or self.command), mock.patch.dict(os.environ, {"GITHUB_SHA": "f" * 40, "GITHUB_RUN_ID": "42"}):
            return publish.promote(self.check, self.payload, self.digest, "vs69/tdlib", self.api)

    def test_android_promotes_only_after_invalidating_complete_release_marker(self):
        receipt = self.invoke()
        self.assertEqual(self.events[1][:2], ("api", "DELETE"))
        self.assertEqual(self.events[2][1:5], ("docker", "buildx", "imagetools", "create"))
        self.assertIn("vs69/tdlib:android", self.events[2])
        self.assertEqual(receipt["reference"], "vs69/tdlib@" + self.digest)
        self.assertFalse(any(event[:2] in (("api", "POST"), ("api", "PATCH")) or "gh" in event for event in self.events))

    def test_registry_failure_keeps_global_success_marker_invalidated(self):
        def failed(*arguments):
            if "create" in arguments:
                raise RuntimeError("registry unavailable")
            return self.command(*arguments)
        with self.assertRaisesRegex(RuntimeError, "registry unavailable"):
            self.invoke(failed)
        self.assertEqual(self.events[-1][:2], ("api", "DELETE"))

    def test_wrong_run_or_payload_cannot_change_any_registry_or_release(self):
        for container, field, value in [(self.check, "run_id", "43"), (self.check, "changed", False), (self.payload, "build_fingerprint", "c" * 64), (self.payload, "tdlib", {"commit": "c" * 40})]:
            with self.subTest(field=field), mock.patch.dict(container, {field: value}):
                with self.assertRaises(ValueError):
                    self.invoke()
                self.assertEqual(self.events, [])

    def test_first_android_publication_does_not_require_complete_github_release(self):
        def missing(path, method="GET", body=None):
            raise urllib.error.HTTPError(path, 404, "Not Found", None, None)
        with mock.patch.object(self.api, "request", missing):
            receipt = self.invoke()
        self.assertEqual(receipt["image"], "vs69/tdlib:android")
        self.assertEqual(self.events[0][1:5], ("docker", "buildx", "imagetools", "create"))


if __name__ == "__main__":
    unittest.main()
