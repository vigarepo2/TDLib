#!/usr/bin/env python3
"""Decide whether the official upstream or the build recipe needs rebuilding."""
import argparse
import base64
import hashlib
import json
import os
import pathlib
import re
import runpy
import urllib.error
from workflow_common import GitHub

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHA = re.compile(r"^[0-9a-f]{40}$")


def fingerprint(root):
    paths = []
    for folder in ("docker", "scripts"):
        paths.extend(p for p in (root / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    paths.extend(root / name for name in ("build.json", ".github/workflows/build-and-publish.yml", "LICENSE", "THIRD_PARTY_NOTICES.md", ".dockerignore"))
    digest = hashlib.sha256()
    for path in sorted(paths):
        if path.exists():
            digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def version_from_cmake(text):
    match = re.search(r"project\s*\(\s*TDLib\s+VERSION\s+([0-9]+\.[0-9]+\.[0-9]+)", text, re.IGNORECASE)
    if not match:
        raise ValueError("Official TDLib CMakeLists.txt does not contain a recognized project version")
    return match.group(1)


def complete_publication(previous):
    if not isinstance(previous, dict) or previous.get("schema") != 1:
        return False
    images = previous.get("images", {})
    artifacts = previous.get("artifacts", {})
    if not isinstance(images, dict) or not isinstance(artifacts, dict):
        return False
    for tag in ("latest", "debian", "alpine", "dev", "debian-dev", "alpine-dev", "android", "packages"):
        item = images.get(tag)
        if not isinstance(item, dict) or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(item.get("digest", ""))):
            return False
        if not isinstance(item.get("reference"), str) or not item["reference"].endswith("@" + item["digest"]):
            return False
    for name in ("tdlib-android.tar.gz", "tdlib-android.aar", "tdlib-windows-x64.tar.gz", "tdlib-apple.tar.gz", "tdlib-web.tar.gz"):
        item = artifacts.get(name)
        if not isinstance(item, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))) or type(item.get("size")) is not int or item["size"] < 1:
            return False
    return True


def requires_build(previous, commit, recipe, force=False):
    return bool(force or not complete_publication(previous) or previous.get("upstream", {}).get("commit") != commit or previous.get("build", {}).get("fingerprint") != recipe)


def configuration():
    path = ROOT / "build.json"
    config = json.loads(path.read_text())
    if config.get("schema") != 1 or config["upstream"]["repository"] != "tdlib/td":
        raise ValueError("Expected official tdlib/td source and configuration schema 1")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", config["upstream"]["ref"]):
        raise ValueError("Invalid upstream ref")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*", config["docker"]["image"]):
        raise ValueError("Expected a Docker Hub namespace/repository")
    if os.environ.get("DOCKER_IMAGE", config["docker"]["image"]) != config["docker"]["image"]:
        raise ValueError("Workflow DOCKER_IMAGE and build.json must name the same repository")
    runpy.run_path(str(ROOT / "scripts/package-android.py"))["pins"](path)
    portable = config["portable"]
    if not SHA.fullmatch(portable["vcpkg_commit"]):
        raise ValueError("vcpkg must be pinned to an exact source commit")
    for name in ("emsdk_version", "macos_minimum", "ios_minimum"):
        if not re.fullmatch(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?", portable[name]):
            raise ValueError(f"Invalid portable toolchain setting: {name}")
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--validate", action="store_true", help="Validate build pins offline, without credentials")
    parser.add_argument("--output", default="check-result.json")
    args = parser.parse_args()
    config = configuration()
    if args.validate:
        print("Build configuration is valid: official source, pinned toolchains and all four Android ABIs.")
        return
    api = GitHub()
    upstream = config["upstream"]["repository"]
    ref = config["upstream"]["ref"]
    commit = api.request(f"/repos/{upstream}/commits/{ref}")["sha"]
    if not SHA.fullmatch(commit):
        raise ValueError("Unexpected upstream commit")
    cmake = api.request(f"/repos/{upstream}/contents/CMakeLists.txt?ref={commit}")
    version = version_from_cmake(base64.b64decode(cmake["content"]).decode())
    # Only an exact official tag at this commit is called an official release.
    tags = api.request(f"/repos/{upstream}/tags?per_page=100")
    official_tag = next((tag["name"] for tag in tags if tag["commit"]["sha"] == commit), None)
    previous = None
    try:
        release = api.request(f"/repos/{api.repository}/releases/tags/latest")
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    else:
        manifest = next((a for a in release["assets"] if a["name"] == "manifest.json"), None)
        if manifest:
            previous = json.loads(api.download(manifest["browser_download_url"]))
    recipe = fingerprint(ROOT)
    changed = requires_build(previous, commit, recipe, args.force)
    result = {
        "schema": 1, "changed": changed,
        "repository": api.repository, "run_id": str(os.environ["GITHUB_RUN_ID"]),
        "head_sha": os.environ["GITHUB_SHA"], "event": os.environ["GITHUB_EVENT_NAME"],
        "upstream": {"repository": upstream, "commit": commit, "version": version, "official_tag": official_tag},
        "build_fingerprint": recipe,
    }
    pathlib.Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            for name, value in {"changed": str(changed).lower(), "commit": commit, "version": version, "fingerprint": recipe, "ndk": config["android"]["ndk_version"], "emsdk": config["portable"]["emsdk_version"]}.items():
                print(f"{name}={value}", file=output)
    print(f"Official TDLib {version} at {commit}; {'build required' if changed else 'already published, no build needed'}")


if __name__ == "__main__":
    main()
