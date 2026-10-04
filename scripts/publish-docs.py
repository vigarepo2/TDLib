#!/usr/bin/env python3
"""Synchronize the same Markdown to Docker Hub without printing credentials."""
import argparse
import json
import os
import pathlib
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]


def request(url, data, token=None, method="POST"):
    headers = {"Content-Type": "application/json", "User-Agent": "vs69-tdlib"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method=method), timeout=60) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-missing-repository", action="store_true")
    args = parser.parse_args()
    username = os.environ.get("DOCKER_USER", "vs69")
    secret = os.environ.get("DOCKER_PASSWORD")
    if not secret:
        raise SystemExit("Set repository secrets DOCKER_USER and DOCKER_PASSWORD. See docs/QUICKSTART.md.")
    token = request("https://hub.docker.com/v2/auth/token", {"identifier": username, "secret": secret})["access_token"]
    image = json.loads((ROOT / "config/build.json").read_text())["docker"]["image"]
    try:
        request(f"https://hub.docker.com/v2/repositories/{image}/", {
            "description": "Prebuilt TDLib for Linux, Android, Windows, Apple and browsers. Daily checks; reusable packages.",
            "full_description": (ROOT / "README.md").read_text(),
        }, token=token, method="PATCH")
    except urllib.error.HTTPError as error:
        if error.code == 404 and args.allow_missing_repository:
            print("Docker Hub repository does not exist yet; documentation will sync after the first successful image publication.")
            return
        raise
    print(f"Updated https://hub.docker.com/r/{image}")


if __name__ == "__main__":
    main()
