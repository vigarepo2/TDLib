#!/usr/bin/env python3
"""Record the provenance and integrity of a portable TDLib package."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest(source: Path, root: Path, platform: str, build: dict) -> dict:
    source, root = source.resolve(), root.resolve()
    commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Expected an exact TDLib Git commit")
    match = re.search(r"project\(TDLib VERSION ([0-9.]+)", (source / "CMakeLists.txt").read_text())
    if not match:
        raise ValueError("Unable to read official TDLib version")
    licenses = root / "licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "LICENSE_1_0.txt", licenses / "TDLib-Boost-1.0.txt")
    # TDLib compiles bundled SQLite/SQLCipher and generated TL parser code too.
    for relative, name in (("sqlite/sqlite/LICENSE", "SQLCipher.txt"),
                           ("td/generate/tl-parser/LICENSE", "tl-parser.txt")):
        shutil.copy2(source / relative, licenses / name)
    distribution = Path(__file__).resolve().parent.parent
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        if (distribution / name).is_file():
            shutil.copy2(distribution / name, licenses / ("distribution-" + name))
    entries = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name not in {"manifest.json", "SHA256SUMS"}:
            # Preserve the full layout: checksums include dependencies and notices.
            entries.append({"path": path.relative_to(root).as_posix(), "size": path.stat().st_size,
                            "sha256": sha256(path)})
    if not entries:
        raise ValueError("Refusing to describe an empty package")
    result = {"schema": 1, "platform": platform, "tdlib": {"repository": "https://github.com/tdlib/td",
              "commit": commit, "version": match.group(1)}, "build": build, "files": entries}
    (root / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    (root / "SHA256SUMS").write_text("".join(f"{entry['sha256']}  {entry['path']}\n" for entry in entries))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--build-json", type=Path, help="JSON object with platform/compiler details")
    args = parser.parse_args()
    build = json.loads(args.build_json.read_text()) if args.build_json else {}
    if not isinstance(build, dict):
        parser.error("--build-json must contain an object")
    result = manifest(args.source, args.root, args.platform, build)
    print(f"Recorded {len(result['files'])} files for {args.platform}: TDLib {result['tdlib']['version']}")


if __name__ == "__main__":
    main()
