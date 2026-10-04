#!/usr/bin/env python3
"""Load the actual JSON ABI, check an API response, without account/network access."""
import ctypes
import json
import os
from pathlib import Path
import sys

library = Path(sys.argv[1]).resolve(strict=True)
directory = os.add_dll_directory(str(library.parent)) if os.name == "nt" else None
try:
    td = ctypes.CDLL(str(library))
    execute = td.td_execute
    execute.restype = ctypes.c_char_p
    execute.argtypes = [ctypes.c_char_p]
    response = json.loads(execute(b'{"@type":"setLogVerbosityLevel","new_verbosity_level":0}'))
    if response.get("@type") != "ok":
        raise RuntimeError(f"TDLib smoke test failed: {response}")
    # String conversion is a useful functional check; it needs no client or login.
    response = json.loads(execute(b'{"@type":"getTextEntities","text":"https://telegram.org"}'))
    if response.get("@type") != "textEntities" or not response.get("entities"):
        raise RuntimeError(f"TDLib text-entity API check failed: {response}")
    print(f"TDLib JSON API smoke test passed: {library.name}")
finally:
    if directory:
        directory.close()
