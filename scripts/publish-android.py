#!/usr/bin/env python3
"""Publish the verified Android image without waiting for other platforms."""
import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
from workflow_common import GitHub

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def run(*arguments):
    return subprocess.check_output(arguments, text=True).strip()


def verify_payload(directory):
    run(sys.executable, str(ROOT / "scripts/package-android.py"), "verify", str(directory))
    return json.loads((directory / "manifest.json").read_text())


def promote(check, payload, image_digest, image, api):
    if (check.get("changed") is not True or check.get("repository") != api.repository
            or check.get("head_sha") != os.environ["GITHUB_SHA"]
            or check.get("run_id") != os.environ["GITHUB_RUN_ID"]):
        raise ValueError("Android publication input does not belong to this changed build")
    if (payload.get("tdlib", {}).get("commit") != check.get("upstream", {}).get("commit")
            or payload.get("build_fingerprint") != check.get("build_fingerprint")):
        raise ValueError("Android package does not match this run's source and build recipes")
    if not DIGEST.fullmatch(image_digest):
        raise ValueError("Invalid Android image digest")
    prefix = f"/repos/{api.repository}"
    try:
        previous = api.request(prefix + "/releases/tags/latest")
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        previous = None
    # The other platforms can fail after Android is ready. Removing the global
    # success marker before promotion makes the next daily check retry them.
    # Only the complete all-platform publisher is allowed to restore that marker.
    if previous:
        for asset in previous["assets"]:
            if asset["name"] == "manifest.json":
                api.request(prefix + f"/releases/assets/{asset['id']}", method="DELETE")
    run("docker", "buildx", "imagetools", "create", "--tag", f"{image}:android", f"{image}@{image_digest}")
    actual = json.loads(run("docker", "buildx", "imagetools", "inspect", f"{image}:android", "--format", "{{json .Manifest}}"))["digest"]
    if not DIGEST.fullmatch(actual):
        raise ValueError("Registry did not return a valid promoted Android digest")
    return {
        "schema": 1, "platform": "android", "upstream": check["upstream"],
        "build_fingerprint": check["build_fingerprint"], "run_id": check["run_id"],
        "image": f"{image}:android", "digest": actual, "reference": f"{image}@{actual}",
        "published_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", type=pathlib.Path, required=True)
    parser.add_argument("--payload", type=pathlib.Path, required=True)
    parser.add_argument("--digest-file", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("android-publication.json"))
    args = parser.parse_args()
    check = json.loads(args.check.read_text())
    payload = verify_payload(args.payload)
    image = json.loads((ROOT / "config/build.json").read_text())["docker"]["image"]
    receipt = promote(check, payload, args.digest_file.read_text().strip(), image, GitHub())
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(f"Published {image}:android ({receipt['digest']}). Android consumers can use it now; other platforms may still be building.")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
            summary.write(f"Android package published as `{image}:android`. TelePlay can now use this verified engine when its pinned inputs match. Other platforms and the complete GitHub release finish separately.\n\nResolved image: `{receipt['reference']}`\n")


if __name__ == "__main__":
    main()
