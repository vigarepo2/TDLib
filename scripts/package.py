#!/usr/bin/env python3
"""Record the provenance and integrity of a portable TDLib package."""
import argparse
import hashlib
import gzip
import os
import tarfile
import tempfile
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
    hashes(root)
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.relative_to(root).as_posix() not in {"manifest.json", "SHA256SUMS", "package-checksums.json"}:
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


def hashes(directory):
    directory = directory.resolve(strict=True)
    result = {}
    for file in sorted(directory.rglob("*")):
        name = file.relative_to(directory).as_posix()
        if name == "package-checksums.json" and file.is_file() and not file.is_symlink():
            continue
        if file.is_symlink():
            target = file.resolve(strict=True)
            if not target.is_relative_to(directory) or not target.is_file() or Path(os.readlink(file)).is_absolute():
                raise ValueError(f"Package symlink must reference an internal file: {name}")
            result[name] = {"symlink": os.readlink(file), "sha256": sha256(target)}
        elif file.is_file():
            result[name] = sha256(file)
        elif not file.is_dir():
            raise ValueError(f"Unsupported package entry: {name}")
    if not result:
        raise ValueError(f"Empty package: {directory}")
    return result


def archive(directory, output):
    directory = directory.resolve(strict=True)
    output = output.resolve()
    if output.is_relative_to(directory):
        raise ValueError("Archive output must be outside its input directory")
    actual = hashes(directory)  # Reject empty packages, escaping links and special files.
    marker = directory / "package-checksums.json"
    if marker.exists() and actual != json.loads(marker.read_text()):
        raise ValueError(f"Cached package checksum mismatch: {directory}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".archive-", dir=output.parent) as temporary:
        staged = Path(temporary) / "package.tar.gz"
        with staged.open("wb") as target, gzip.GzipFile(filename="", fileobj=target, mode="wb", mtime=0) as compressed, tarfile.open(fileobj=compressed, mode="w") as bundle:
            for file in sorted(directory.rglob("*")):
                if file.is_dir():
                    continue
                info = bundle.gettarinfo(str(file), arcname=file.relative_to(directory).as_posix())
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                info.mode = 0o777 if file.is_symlink() else (0o755 if file.stat().st_mode & 0o111 else 0o644)
                if file.is_symlink():
                    bundle.addfile(info)
                else:
                    with file.open("rb") as source:
                        bundle.addfile(info, source)
        os.replace(staged, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    item = commands.add_parser("manifest")
    item.add_argument("--source", type=Path, required=True)
    item.add_argument("--root", type=Path, required=True)
    item.add_argument("--platform", required=True)
    item.add_argument("--build-json", type=Path)
    for command in ("record", "verify", "archive"):
        item = commands.add_parser(command)
        item.add_argument("directory", type=Path)
        if command == "archive":
            item.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "manifest":
        build = json.loads(args.build_json.read_text(encoding="utf-8-sig")) if args.build_json else {}
        if not isinstance(build, dict):
            parser.error("--build-json must contain an object")
        result = manifest(args.source, args.root, args.platform, build)
        print(f"Recorded {len(result['files'])} files for {args.platform}")
    elif args.command == "archive":
        archive(args.directory, args.output)
    else:
        marker = args.directory / "package-checksums.json"
        actual = hashes(args.directory)
        if args.command == "record":
            marker.write_text(json.dumps(actual, sort_keys=True, indent=2) + "\n")
        elif actual != json.loads(marker.read_text()):
            raise ValueError(f"Cached package checksum mismatch: {args.directory}")


if __name__ == "__main__":
    main()

