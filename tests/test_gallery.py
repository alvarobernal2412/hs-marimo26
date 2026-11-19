import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.skipif(shutil.which("marimo") is None and not Path(sys.prefix, "Scripts", "marimo.exe").exists(), reason="marimo missing")
def test_gallery_serves_notebooks_folder():
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "marimo", "run", str(ROOT / "notebooks"), "--headless", "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(60):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
                    assert r.status == 200
                    return
            except OSError:
                time.sleep(0.5)
        pytest.fail("gallery did not start")
    finally:
        proc.terminate()
