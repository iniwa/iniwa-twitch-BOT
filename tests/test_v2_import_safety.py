import os
import subprocess
import sys


def test_import_has_no_thread_network_directory_or_file_write_side_effects():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    source = r'''
import builtins
import os
import socket
import threading

def boom(*args, **kwargs):
    raise AssertionError("import attempted a forbidden side effect")

threading.Thread.start = boom
socket.socket.connect = boom
os.mkdir = boom
os.makedirs = boom
original_open = builtins.open
def guarded_open(file, mode="r", *args, **kwargs):
    if any(flag in mode for flag in ("w", "a", "x", "+")):
        raise AssertionError("import attempted a file write")
    return original_open(file, mode, *args, **kwargs)
builtins.open = guarded_open
import twitchbot
assert callable(twitchbot.create_app)
from twitchbot.settings import AppSettings
from twitchbot.container import Container
from twitchbot.adapters import AdapterSet
from twitchbot.adapters.persistence import SQLiteDatabase
from twitchbot.migration import CandidateImporter, LegacySourceInspector
assert AppSettings().enable_vod_download is False
assert Container().adapters.twitch.status().code == "not_configured"
assert AdapterSet.unavailable().media.status().available is False
assert SQLiteDatabase
assert LegacySourceInspector
assert CandidateImporter
'''
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(root, "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-B", "-c", source],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
