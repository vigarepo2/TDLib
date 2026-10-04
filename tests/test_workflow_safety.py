import copy
import importlib.util
import io
import json
import pathlib
import sys
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


check = module("check-upstream")
cleanup = module("cleanup-noop")
package = module("package-release")


class UpdateTests(unittest.TestCase):
    def test_changes_and_incomplete_publications_rebuild(self):
        previous = {"schema": 1, "upstream": {"commit": "a" * 40}, "build": {"fingerprint": "b" * 64}}
        self.assertTrue(check.requires_build(previous, "a" * 40, "b" * 64))
        previous["images"] = {tag: {"digest": "sha256:" + "d" * 64, "reference": "vs69/tdlib@sha256:" + "d" * 64} for tag in ("latest", "debian", "alpine", "dev", "debian-dev", "alpine-dev", "android", "packages")}
        previous["artifacts"] = {name: {"sha256": "e" * 64, "size": 5} for name in ("tdlib-android.tar.gz", "tdlib-android.aar", "tdlib-windows-x64.tar.gz", "tdlib-apple.tar.gz", "tdlib-web.tar.gz")}
        self.assertFalse(check.requires_build(previous, "a" * 40, "b" * 64))
        self.assertTrue(check.requires_build(previous, "c" * 40, "b" * 64))
        self.assertTrue(check.requires_build(previous, "a" * 40, "d" * 64))
        self.assertTrue(check.requires_build(previous, "a" * 40, "b" * 64, force=True))
        self.assertTrue(check.requires_build(None, "a" * 40, "b" * 64))
        self.assertTrue(check.requires_build({}, "a" * 40, "b" * 64))

    def test_documentation_does_not_trigger_native_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "scripts").mkdir()
            (root / "scripts/build.sh").write_text("first")
            first = check.fingerprint(root)
            (root / "README.md").write_text("new documentation")
            self.assertEqual(first, check.fingerprint(root))
            (root / "scripts/build.sh").write_text("second")
            self.assertNotEqual(first, check.fingerprint(root))

    def test_only_recognized_upstream_version_is_used(self):
        self.assertEqual(check.version_from_cmake("project(TDLib VERSION 1.8.67 LANGUAGES CXX C)"), "1.8.67")
        with self.assertRaises(ValueError):
            check.version_from_cmake("project(somethingelse VERSION 1.2.3)")


class CleanupSafetyTests(unittest.TestCase):
    def setUp(self):
        self.repository = "vigarepo2/TDLib"
        self.run = {"id": 9, "repository": {"full_name": self.repository}, "head_repository": {"full_name": self.repository}, "workflow_id": 77, "path": cleanup.BUILD_PATH, "event": "schedule", "status": "completed", "conclusion": "success", "head_sha": "c" * 40}
        self.marker = {"schema": 1, "changed": False, "repository": self.repository, "event": "schedule", "run_id": "9", "head_sha": "c" * 40, "upstream": {"commit": "a" * 40}, "build_fingerprint": "b" * 64}

    def test_only_successful_scheduled_target_workflow_is_eligible(self):
        self.assertTrue(cleanup.eligible_run(self.run, self.repository, 77))
        for field, wrong in [("event", "workflow_dispatch"), ("event", "push"), ("conclusion", "failure"), ("conclusion", "cancelled"), ("status", "in_progress"), ("workflow_id", 78), ("path", cleanup.CLEANUP_PATH), ("head_repository", {"full_name": "attacker/fork"})]:
            with self.subTest(field=field, value=wrong):
                altered = dict(self.run, **{field: wrong})
                self.assertFalse(cleanup.eligible_run(altered, self.repository, 77))

    def test_builds_or_mismatched_markers_are_retained(self):
        self.assertTrue(cleanup.eligible_marker(self.marker, self.run, self.repository))
        for field, wrong in [("changed", True), ("changed", 0), ("run_id", "10"), ("head_sha", "d" * 40), ("repository", "attacker/fork"), ("event", "workflow_dispatch")]:
            with self.subTest(field=field):
                altered = dict(self.marker, **{field: wrong})
                self.assertFalse(cleanup.eligible_marker(altered, self.run, self.repository))

    def test_marker_zip_rejects_extra_paths(self):
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as archive:
            archive.writestr("check-result.json", json.dumps(self.marker))
            archive.writestr("../payload", "untrusted")
        with self.assertRaises(ValueError):
            cleanup.read_marker(payload.getvalue())

    def test_marker_zip_accepts_only_small_expected_file(self):
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as archive:
            archive.writestr("check-result.json", json.dumps(self.marker))
        self.assertEqual(cleanup.read_marker(payload.getvalue()), self.marker)


class PackageIntegrityTests(unittest.TestCase):
    def test_changed_or_added_cache_files_are_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            native = root / "native.so"
            native.write_bytes(b"compiled library")
            hashes = package.hashes(root)
            native.write_bytes(b"broken library")
            self.assertNotEqual(hashes, package.hashes(root))
            native.write_bytes(b"compiled library")
            (root / "extra.so").write_bytes(b"unexpected")
            self.assertNotEqual(hashes, package.hashes(root))


if __name__ == "__main__":
    unittest.main()
