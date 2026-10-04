"""Run an account-free query using Python's built-in ctypes (no pip package)."""
import ctypes
import json
import os

tdlib = ctypes.CDLL(os.environ.get("TDLIB_LIBRARY_PATH", "libtdjson.so"))
tdlib.td_execute.argtypes = [ctypes.c_char_p]
tdlib.td_execute.restype = ctypes.c_char_p
request = {"@type": "getOption", "name": "version"}
response = tdlib.td_execute(json.dumps(request).encode("utf-8"))
if response is None:
    raise RuntimeError("TDLib did not return a synchronous response")
print(json.loads(response.decode("utf-8")))
