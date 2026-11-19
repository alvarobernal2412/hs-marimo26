"""Brings the notebooks of a student bundle up to date from the GitHub Releases of this repository.

Standard library only: it runs with the bundled Python before anything else starts. Every failure is swallowed: the student
must always be able to start with the notebooks they already have.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO = "alvarobernal2412/hs-marimo26"
KEEP = ("data", "provenance")  # folders under notebooks/ that an update never touches
TIMEOUT = 15


def read_version(root: Path) -> dict:
    try:
        found = json.loads((Path(root) / "version.json").read_text(encoding="utf8"))
        return {"runtime": int(found.get("runtime", 0)), "notebooks": int(found.get("notebooks", 0))}
    except (OSError, ValueError):
        return {"runtime": 0, "notebooks": 0}


def urlopen_json(url: str):
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "hs-marimo26"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.load(response)


def download_to(url: str, dest) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "hs-marimo26"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response, open(dest, "wb") as out:
        shutil.copyfileobj(response, out)


def latest_release(repo: str = REPO, fetch=urlopen_json) -> dict | None:
    """The newest `notebooks-N` release as `{notebooks, zip_url, min_runtime}`, or None (also on any error)."""
    try:
        best = None
        for item in fetch(f"https://api.github.com/repos/{repo}/releases"):
            match = re.fullmatch(r"notebooks-(\d+)", item.get("tag_name", ""))
            asset = next((a for a in item.get("assets", []) if a.get("name") == "notebooks.zip"), None)
            if not match or not asset or (best and int(match[1]) <= best["notebooks"]):
                continue
            try:
                min_runtime = int(json.loads(item.get("body") or "{}").get("min_runtime", 0))
            except ValueError:
                min_runtime = 0
            best = {"notebooks": int(match[1]), "zip_url": asset["browser_download_url"], "min_runtime": min_runtime}
        return best
    except Exception:
        return None


def apply_release(root: Path, release: dict, download=download_to) -> str:
    """One of "updated", "current", "needs-runtime", "failed". The notebooks folder changes only after the whole zip checked out."""
    root = Path(root)
    version = read_version(root)
    if release["notebooks"] <= version["notebooks"]:
        return "current"
    if release["min_runtime"] > version["runtime"]:
        print("A newer version of the notebooks needs a new download of this package. Please download it again from the course page.")
        return "needs-runtime"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "notebooks.zip"
            download(release["zip_url"], archive)
            with zipfile.ZipFile(archive) as z:
                if z.testzip() is not None:
                    return "failed"
                staged = Path(tmp) / "staged"
                z.extractall(staged)
            target = root / "notebooks"
            target.mkdir(exist_ok=True)
            for item in staged.iterdir():
                if item.name in KEEP:
                    continue
                destination = target / item.name
                if destination.is_dir():
                    shutil.rmtree(destination)
                elif destination.exists():
                    destination.unlink()
                shutil.move(str(item), destination)
        (root / "version.json").write_text(json.dumps({**version, "notebooks": release["notebooks"]}), encoding="utf8")
        return "updated"
    except Exception:
        return "failed"


def main(root: Path) -> int:
    try:
        release = latest_release()
        if release:
            apply_release(Path(root), release)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]))
