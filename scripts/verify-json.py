#!/usr/bin/env python3
"""Exercise the real TDLib JSON ABI without an account or network connection."""

import argparse
from contextlib import nullcontext
import ctypes
import json
import os
from pathlib import Path
import sys


def verify(library: str, expected_version: str = "", expected_commit: str = "") -> dict:
    tdlib = ctypes.CDLL(library)
    tdlib.td_execute.argtypes = [ctypes.c_char_p]
    tdlib.td_execute.restype = ctypes.c_char_p

    def execute(request: dict) -> dict:
        response = tdlib.td_execute(json.dumps(request).encode("utf-8"))
        if not response:
            raise RuntimeError(f"TDLib returned no synchronous response: {request['@type']}")
        result = json.loads(response.decode("utf-8"))
        if result.get("@type") == "error":
            raise RuntimeError(f"TDLib rejected {request['@type']}: {result}")
        return result

    execute({"@type": "setLogVerbosityLevel", "new_verbosity_level": 0})
    values = {}
    for option, expected in (("version", expected_version), ("commit_hash", expected_commit)):
        result = execute({"@type": "getOption", "name": option})
        if result.get("@type") != "optionValueString" or not result.get("value"):
            raise RuntimeError(f"Unexpected {option} response: {result}")
        values[option] = result["value"]
        if expected and result["value"] != expected:
            raise RuntimeError(f"Expected {option}={expected}, loaded {result['value']}")

    parsed = execute({
        "@type": "parseTextEntities",
        "text": "<b>TDLib</b>",
        "parse_mode": {"@type": "textParseModeHTML"},
    })
    if (parsed.get("@type") != "formattedText" or parsed.get("text") != "TDLib"
            or len(parsed.get("entities", [])) != 1
            or parsed["entities"][0].get("type", {}).get("@type") != "textEntityTypeBold"
            or parsed["entities"][0].get("offset") != 0
            or parsed["entities"][0].get("length") != 5):
        raise RuntimeError(f"Offline text parsing returned an unexpected result: {parsed}")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", nargs="?", default="libtdjson.so")
    parser.add_argument("--version", default="")
    parser.add_argument("--commit", default="")
    args = parser.parse_args()
    try:
        directory = os.add_dll_directory(str(Path(args.library).resolve().parent)) if os.name == "nt" else nullcontext()
        with directory:
            values = verify(args.library, args.version, args.commit)
    except (OSError, RuntimeError, ValueError, AttributeError) as error:
        print(f"TDLib smoke test failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok", **values, "offline_json_test": "passed"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
