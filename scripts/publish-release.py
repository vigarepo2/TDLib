#!/usr/bin/env python3
"""Promote a fully tested build, then record success in one rolling release."""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import subprocess
import urllib.error
from workflow_common import GitHub

DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def digest(value):
    if not DIGEST.fullmatch(value):
        raise ValueError("Invalid OCI digest")
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=pathlib.Path, default=pathlib.Path("collected"))
    parser.add_argument("--release", type=pathlib.Path, default=pathlib.Path("release"))
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    image = json.loads((root / "config/build.json").read_text())["docker"]["image"]
    check = json.loads((args.artifacts / "upstream-check/check-result.json").read_text())
    if check["changed"] is not True or check["head_sha"] != os.environ["GITHUB_SHA"] or check["run_id"] != os.environ["GITHUB_RUN_ID"]:
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
        (args.release / name).write_bytes(candidates[0].read_bytes())
    artifacts = {name: {"sha256": hashlib.sha256((args.release / name).read_bytes()).hexdigest(), "size": (args.release / name).stat().st_size} for name in required}
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


if __name__ == "__main__":
    main()
