#!/usr/bin/env python3
"""Promote a fully tested build, then record success in one rolling release."""
import argparse
import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from package import sha256
from workflow_common import GitHub, SafeRedirect

DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
ROOT = pathlib.Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def digest(value):
    if not DIGEST.fullmatch(value):
        raise ValueError("Invalid OCI digest")
    return value


def publish_release(args):
    root = pathlib.Path(__file__).resolve().parents[1]
    image = json.loads((root / "build.json").read_text())["docker"]["image"]
    check = json.loads((args.artifacts / "upstream-check/check-result.json").read_text())
    if (check["changed"] is not True or check.get("repository") != os.environ["GITHUB_REPOSITORY"]
            or check["head_sha"] != os.environ["GITHUB_SHA"] or check["run_id"] != os.environ["GITHUB_RUN_ID"]):
        raise ValueError("Publication input does not belong to this changed build")
    sources = {}
    for variant in ("debian", "alpine"):
        for target in ("runtime", "devel"):
            sources[f"{variant}{'-dev' if target == 'devel' else ''}"] = [digest(json.loads((args.artifacts / f"digests-linux-{variant}-{arch}/digests.json").read_text())[target]) for arch in ("amd64", "arm64")]
    sources["latest"] = sources["debian"]
    sources["dev"] = sources["debian-dev"]
    for target in ("android", "packages"):
        sources[target] = [digest((args.artifacts / f"digest-{target}/digest.txt").read_text().strip())]
    args.release.mkdir(parents=True, exist_ok=True)
    required = ["tdlib-android.tar.gz", "tdlib-android.aar", "tdlib-windows-x64.tar.gz", "tdlib-apple.tar.gz", "tdlib-web.tar.gz"]
    for name in required:
        candidates = list(args.artifacts.rglob(name))
        if len(candidates) != 1:
            raise ValueError(f"Expected exactly one {name}, found {len(candidates)}")
        if candidates[0].is_symlink() or not candidates[0].is_file() or candidates[0].stat().st_size == 0:
            raise ValueError(f"Empty or invalid release payload: {name}")
        shutil.copyfile(candidates[0], args.release / name)
    artifacts = {name: {"sha256": sha256(args.release / name), "size": (args.release / name).stat().st_size} for name in required}
    (args.release / "SHA256SUMS").write_text("".join(f"{info['sha256']}  {name}\n" for name, info in sorted(artifacts.items())))
    api = GitHub()
    prefix = f"/repos/{api.repository}"
    try:
        previous = api.request(prefix + "/releases/tags/latest")
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        previous = None
    # Invalidate the success marker BEFORE advancing any mutable tag. If any
    # publish operation fails, the next scheduled check retries the full update.
    if previous:
        for asset in previous["assets"]:
            if asset["name"] == "manifest.json":
                api.request(prefix + f"/releases/assets/{asset['id']}", method="DELETE")
    images = {}
    for tag, values in sources.items():
        run("docker", "buildx", "imagetools", "create", "--tag", f"{image}:{tag}", *[f"{image}@{value}" for value in values])
        current = digest(json.loads(run("docker", "buildx", "imagetools", "inspect", f"{image}:{tag}", "--format", "{{json .Manifest}}"))["digest"])
        images[tag] = {"digest": current, "reference": f"{image}@{current}"}
        print(f"Published {image}:{tag} ({current})")
    source = check["upstream"]
    manifest = {
        "schema": 1, "upstream": source,
        "build": {"fingerprint": check["build_fingerprint"], "repository": api.repository, "commit": os.environ["GITHUB_SHA"], "run_id": os.environ["GITHUB_RUN_ID"], "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()},
        "images": images, "artifacts": artifacts,
    }
    (args.release / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    official = source.get("official_tag")
    status = f"Official upstream tag `{official}`." if official else "Development snapshot of official upstream master; this is not a tagged upstream release."
    notes = (f"Prebuilt TDLib **{source['version']}**, upstream commit [`{source['commit']}`](https://github.com/{source['repository']}/commit/{source['commit']}).\n\n{status}\n\n"
             f"Docker Hub: https://hub.docker.com/r/{image}\n\nThis rolling release replaces the previous packages. `manifest.json` records source, recipes, checksums and image digests. Verify downloads with `sha256sum -c SHA256SUMS`.\n\n"
             f"Build: https://github.com/{api.repository}/actions/runs/{os.environ['GITHUB_RUN_ID']}\n")
    title = f"TDLib {source['version']} · {source['commit'][:7]}"
    fields = {"tag_name": "latest", "target_commitish": os.environ["GITHUB_SHA"], "name": title, "body": notes, "draft": False, "prerelease": not bool(official)}
    if previous:
        api.request(prefix + f"/releases/{previous['id']}", method="PATCH", body=fields)
        api.request(prefix + "/git/refs/tags/latest", method="PATCH", body={"sha": os.environ["GITHUB_SHA"], "force": True})
    else:
        api.request(prefix + "/releases", method="POST", body=fields)
    # Ordinary payloads and release metadata first; the checker's success marker last.
    run("gh", "release", "upload", "latest", "--repo", api.repository, "--clobber", *[str(args.release / name) for name in [*required, "SHA256SUMS"]])
    run("gh", "release", "upload", "latest", "--repo", api.repository, "--clobber", str(args.release / "manifest.json"))
    print("Rolling release is complete; future unchanged checks will skip compilation.")

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


def publish_android(args):
    check = json.loads(args.check.read_text())
    payload = verify_payload(args.payload)
    image = json.loads((ROOT / "build.json").read_text())["docker"]["image"]
    receipt = promote(check, payload, args.digest_file.read_text().strip(), image, GitHub())
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(f"Published {image}:android ({receipt['digest']}). Android consumers can use it now; other platforms may still be building.")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
            summary.write(f"Android package published as `{image}:android`. TelePlay can now use this verified engine when its pinned inputs match. Other platforms and the complete GitHub release finish separately.\n\nResolved image: `{receipt['reference']}`\n")

def hub_request(url, data, token=None, method="POST"):
    headers = {"Content-Type": "application/json", "User-Agent": "vs69-tdlib"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.build_opener(SafeRedirect()).open(urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method=method), timeout=60) as response:
        content = response.read()
        return json.loads(content) if content else {}


def publish_docs(args):
    username = os.environ.get("DOCKER_USER", "vs69")
    secret = os.environ.get("DOCKER_PASSWORD")
    if not secret:
        raise SystemExit("Set repository secrets DOCKER_USER and DOCKER_PASSWORD. See README.md.")
    token = hub_request("https://hub.docker.com/v2/auth/token", {"identifier": username, "secret": secret})["access_token"]
    image = json.loads((ROOT / "build.json").read_text())["docker"]["image"]
    try:
        hub_request(f"https://hub.docker.com/v2/repositories/{image}/", {
            "description": "Prebuilt TDLib for Linux, Android, Windows, macOS, iOS and WebAssembly. Images and native packages.",
            "full_description": (ROOT / "README.md").read_text(),
        }, token=token, method="PATCH")
    except urllib.error.HTTPError as error:
        if error.code == 404 and args.allow_missing_repository:
            print("Docker Hub repository does not exist yet; documentation will sync after the first successful image publication.")
            return
        raise
    print(f"Updated https://hub.docker.com/r/{image}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    item = commands.add_parser("release")
    item.add_argument("--artifacts", type=pathlib.Path, default=pathlib.Path("collected"))
    item.add_argument("--release", type=pathlib.Path, default=pathlib.Path("release"))
    item = commands.add_parser("android")
    item.add_argument("--check", type=pathlib.Path, required=True)
    item.add_argument("--payload", type=pathlib.Path, required=True)
    item.add_argument("--digest-file", type=pathlib.Path, required=True)
    item.add_argument("--output", type=pathlib.Path, default=pathlib.Path("android-publication.json"))
    item = commands.add_parser("docs")
    item.add_argument("--allow-missing-repository", action="store_true")
    args = parser.parse_args()
    {"release": publish_release, "android": publish_android, "docs": publish_docs}[args.command](args)


if __name__ == "__main__":
    main()
