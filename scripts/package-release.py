#!/usr/bin/env python3
"""Hash cached outputs and create deterministic, portable release archives."""
import argparse
import gzip
import hashlib
import json
import pathlib
import tarfile


def hashes(directory):
    result = {}
    for file in sorted(directory.rglob("*")):
        if file.is_file() and file.name != "package-checksums.json":
            result[file.relative_to(directory).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    if not result:
        raise ValueError(f"Empty package: {directory}")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("record", "verify", "archive"))
    parser.add_argument("directory", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    marker = args.directory / "package-checksums.json"
    if args.command == "record":
        marker.write_text(json.dumps(hashes(args.directory), sort_keys=True, indent=2) + "\n")
    elif args.command == "verify":
        if hashes(args.directory) != json.loads(marker.read_text()):
            raise ValueError(f"Cached package checksum mismatch: {args.directory}")
    else:
        if not args.output:
            parser.error("archive requires --output")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("wb") as target, gzip.GzipFile(filename="", fileobj=target, mode="wb", mtime=0) as compressed, tarfile.open(fileobj=compressed, mode="w") as archive:
            for file in sorted(args.directory.rglob("*")):
                if file.is_dir():
                    continue
                info = archive.gettarinfo(str(file), arcname=file.relative_to(args.directory).as_posix())
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                if file.is_file() and not file.is_symlink():
                    with file.open("rb") as source:
                        archive.addfile(info, source)
                else:
                    archive.addfile(info)


if __name__ == "__main__":
    main()
