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


GALLERY = {
    "00_lecture-initial-analysis.py": "00 Lecture - Initial Analysis",
    "01_assignment-initial-analysis.py": "01 Assignment - Initial Analysis",
    "02_lecture-process-map.py": "02 Lecture - Process Map",
    "03_assignment-process-map.py": "03 Assignment - Process Map",
    "04_tutorial-process-map.py": "04 Tutorial - Process Map",
}


def test_the_gallery_lists_the_notebooks_in_course_order_under_their_titles():
    """`marimo run notebooks` lists every notebook of the folder, by file name, under the title it sets."""
    assert sorted(p.name for p in (ROOT / "notebooks").glob("[0-9][0-9]_*.py")) == list(GALLERY)
    for name, title in GALLERY.items():
        source = (ROOT / "notebooks" / name).read_text(encoding="utf8")
        assert f'app_title="{title}"' in source, name
        assert f'title = "{title}"' in source, name  # the opengraph title, the same


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
