"""Brings the notebooks of a student bundle up to date from the latest GitHub Release of this repository.

Standard library only: it runs with the bundled Python before anything else starts. Every failure is swallowed: the student
must always be able to start with the notebooks they already have.

Versions are `MAJOR.MINOR.PATCH`. The bundle holds one (`version.json`). A release with the same MAJOR only changes the notebooks,
so it is applied; a newer MAJOR changes the package itself (Python, libraries, data folder), so the student is told to paste the install line again (it downloads the new package).

`manifest.json` (in the bundle, and in each release's `notebooks.zip`) lists the notebook files a release ships and a hash of the
libraries they were made for. It is what lets an update remove a notebook that a release dropped, and refuse notebooks that need
libraries this bundle does not have (a release that changed them without a new MAJOR).

A release can be published again under the same number with other contents. The manifest therefore also names the build (`build`, the
commit it was made from), and each release publishes its manifest as a small file of its own. When the numbers are equal and the
builds differ, the release is applied like a newer one of the same MAJOR.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPO = "alvarobernal2412/hs-marimo26"
KEEP = ("data", "provenance")  # folders under notebooks/ whose other files an update never touches
MANIFEST = "manifest.json"
TIMEOUT = 15
Version = tuple[int, int, int]


def parse_version(text: str) -> Version | None:
    """`v1.2.3` or `1.2.3` as (1, 2, 3); None for anything else."""
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(text).strip())
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def read_version(root: Path) -> Version:
    try:
        found = json.loads((Path(root) / "version.json").read_text(encoding="utf8"))
        return parse_version(found["version"]) or (0, 0, 0)
    except (OSError, ValueError, KeyError):
        return (0, 0, 0)


def read_manifest(text: str | bytes | None) -> dict:
    """`{"files": [...], "requirements": "..."}` from a manifest's text; empty for none or one that cannot be read."""
    try:
        found = json.loads(text) if text else {}
        return found if isinstance(found, dict) else {}
    except ValueError:
        return {}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def redirect_target(url: str) -> str | None:
    """Where `url` redirects to, without going there."""
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "hs-marimo26"})
    try:
        with urllib.request.build_opener(_NoRedirect).open(request, timeout=TIMEOUT) as response:
            return response.headers.get("Location")
    except urllib.error.HTTPError as answer:  # a redirect that is not followed arrives as an "error" carrying the headers
        return answer.headers.get("Location")


def download_to(url: str, dest) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "hs-marimo26"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response, open(dest, "wb") as out:
        shutil.copyfileobj(response, out)


def latest_release(repo: str = REPO, resolve=redirect_target) -> dict | None:
    """The latest published release as `{version, zip_url}`, or None (also on any error). Drafts and pre-releases never count.

    The public "latest release" page redirects to `.../tag/<version>`. That is not an API call, so a whole classroom behind one
    address is never turned away for asking too often."""
    try:
        location = resolve(f"https://github.com/{repo}/releases/latest") or ""
        tag = location.rsplit("/tag/", 1)[1] if "/tag/" in location else ""
        version = parse_version(tag)
        if version is None:
            return None
        files = f"https://github.com/{repo}/releases/download/{tag}"
        return {"version": version, "zip_url": f"{files}/notebooks.zip", "manifest_url": f"{files}/{MANIFEST}"}
    except Exception:
        return None


def _shipped(names, notebooks: Path) -> list[Path]:
    """The files under `notebooks` that a manifest names, leaving out anything an update must never remove: the kept folders, and
    whatever is not plainly inside the notebooks folder."""
    found = []
    for name in names if isinstance(names, list) else []:
        parts = Path(str(name)).parts
        if not parts or parts[0] in KEEP or ".." in parts or Path(str(name)).is_absolute() or str(name).startswith(("/", "\\")):
            continue
        found.append(notebooks.joinpath(*parts))
    return found


def _remove_dropped(notebooks: Path, before: dict, after: dict) -> None:
    """Delete the notebook files the installed release shipped and the new one does not. A file the student added was never in a
    list, so it stays."""
    still = set(_shipped(after.get("files"), notebooks))
    for path in _shipped(before.get("files"), notebooks):
        if path in still or not path.is_file():
            continue
        path.unlink()
        folder = path.parent
        while folder != notebooks and not any(folder.iterdir()):  # a folder left empty goes too
            folder.rmdir()
            folder = folder.parent


def published_again(before: dict, release: dict, download=download_to) -> bool:
    """Whether the release is another build than the installed one of the same version. Only when both say which build they are: a
    package built by hand, a release without its manifest and a manifest that cannot be fetched all count as the same build."""
    try:
        if not before.get("build") or not release.get("manifest_url"):
            return False
        with tempfile.TemporaryDirectory() as tmp:
            fetched = Path(tmp) / MANIFEST
            download(release["manifest_url"], fetched)
            build = read_manifest(fetched.read_text(encoding="utf8")).get("build")
        return bool(build) and build != before["build"]
    except Exception:
        return False


def apply_release(root: Path, release: dict, download=download_to) -> str:
    """One of "updated", "current", "needs-package", "failed". The notebooks folder changes only after the whole zip checked out."""
    root = Path(root)
    installed, wanted = read_version(root), release["version"]
    if wanted < installed:
        return "current"
    try:
        before = read_manifest((root / MANIFEST).read_text(encoding="utf8"))
    except OSError:
        before = {}
    if wanted == installed and not published_again(before, release, download):
        return "current"
    if wanted[0] != installed[0]:
        print("A new version of the course package is available. Please paste the install line from START-HERE.txt again to download it.")
        return "needs-package"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "notebooks.zip"
            download(release["zip_url"], archive)
            with zipfile.ZipFile(archive) as z:
                if z.testzip() is not None:
                    return "failed"
                after = read_manifest(z.read(MANIFEST)) if MANIFEST in z.namelist() else {}
                if before.get("requirements") and after.get("requirements") and before["requirements"] != after["requirements"]:
                    # these notebooks were made for other libraries than this bundle has: they would fail when they start
                    print("A new version of the course package is available. Please paste the install line from START-HERE.txt again to download it.")
                    return "needs-package"
                staged = Path(tmp) / "staged"
                z.extractall(staged)
            target = root / "notebooks"
            target.mkdir(exist_ok=True)
            for item in staged.iterdir():
                if item.name == MANIFEST or item.name == "provenance":
                    continue
                destination = target / item.name
                if item.name in KEEP:  # the datasets: the files of the release are added, the others stay as they are
                    shutil.copytree(item, destination, dirs_exist_ok=True)
                    continue
                if destination.is_dir():
                    shutil.rmtree(destination)
                elif destination.exists():
                    destination.unlink()
                shutil.move(str(item), destination)
            if before.get("files") and after.get("files"):
                _remove_dropped(target, before, after)
            if after:
                (root / MANIFEST).write_text(json.dumps(after), encoding="utf8")
        (root / "version.json").write_text(json.dumps({"version": ".".join(map(str, wanted))}), encoding="utf8")
        return "updated"
    except Exception:
        return "failed"


def check(root: Path, find=latest_release) -> str:
    """Update if there is something newer; says what happened: `apply_release`'s answer, or "unknown" (no release was found)."""
    try:
        release = find()
        return apply_release(Path(root), release) if release else "unknown"
    except Exception:
        return "unknown"


def main(root: Path) -> int:
    check(root)
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]))
