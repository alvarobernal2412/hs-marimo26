"""Builds the student zip of one operating system: standalone Python 3.13 + pinned packages + launcher + notebooks + datasets.

Run it on the operating system it builds for (the packages are installed with that system's own pip):
    python build/build_runtime.py --os windows-x64 --data-dir DATA --out OUT --version 1.0.0
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

TARGETS = {"windows-x64": "x86_64-pc-windows-msvc", "macos-arm64": "aarch64-apple-darwin", "macos-x64": "x86_64-apple-darwin"}
LAUNCHER_AT_ROOT = {"windows-x64": "Start.bat", "macos-arm64": "Start.command", "macos-x64": "Start.command"}
RELEASES = "https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest"


def render_version_json(version: str) -> str:
    return json.dumps({"version": version})


def find_python_asset(release: dict, target: str) -> str:
    pattern = re.compile(rf"cpython-3\.13\.\d+\+\d+-{re.escape(target)}-install_only\.tar\.gz")
    for asset in release["assets"]:
        if pattern.fullmatch(asset["name"]):
            return asset["browser_download_url"]
    raise LookupError(f"no Python 3.13 build for {target}")


def assemble(repo: Path, python_dir: Path, data_dir: Path, out_dir: Path, os_name: str, version: str) -> Path:
    """Lays the bundle out and zips it; returns the zip's path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"hs-marimo26-v{version}-{os_name}.zip"
    entries: list[tuple[Path, str, int]] = []  # (file, name in zip, unix mode)

    def add_tree(source: Path, prefix: str) -> None:
        for file in sorted(source.rglob("*")):
            if file.is_file() and "__pycache__" not in file.parts and file.suffix != ".pyc":
                executable = file.stat().st_mode & 0o111 or prefix == "python/bin"
                entries.append((file, f"{prefix}/{file.relative_to(source).as_posix()}", 0o755 if executable else 0o644))

    add_tree(python_dir, "python")
    add_tree(repo / "notebooks", "notebooks")
    for name in ("start.py", "update.py", "consent.py"):
        entries.append((repo / "launcher" / name, f"launcher/{name}", 0o644))
    launcher = LAUNCHER_AT_ROOT[os_name]
    entries.append((repo / "launcher" / launcher, launcher, 0o755))
    for file in sorted(Path(data_dir).glob("*")):
        entries.append((file, f"notebooks/data/{file.name}", 0o644))
    student_readme = repo / "launcher" / "README-students.md"
    if student_readme.exists():
        entries.append((student_readme, "README-students.md", 0o644))
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        seen = set()
        for file, name, mode in entries:
            if name in seen:
                continue
            seen.add(name)
            info = zipfile.ZipInfo.from_file(file, name)
            info.external_attr = (mode | 0o100000) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(file, "rb") as src, z.open(info, "w", force_zip64=True) as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
        z.writestr("version.json", render_version_json(version))
    return zip_path


def export_csv(interpreter: Path, parquet: Path, out: Path) -> None:
    """Writes the Dhana log as a `.csv` next to its `.xes`, for the tools that read neither parquet nor the notebooks' loader."""
    code = "import sys, pandas as pd; pd.read_parquet(sys.argv[1]).to_csv(sys.argv[2], index=False)"
    subprocess.run([str(interpreter), "-s", "-c", code, str(parquet), str(out)], check=True)


def github_json(url: str, token: str | None = None, attempts: int = 3, sleep=time.sleep, opener=urllib.request.urlopen):
    """A GitHub API answer. Sends the token when there is one (the unauthenticated limit is 60 calls an hour per address, which CI
    runners share) and retries, waiting longer each time, when GitHub says it is rate limited or has a hiccup."""
    headers = {"User-Agent": "hs-marimo26", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(attempts):
        try:
            with opener(urllib.request.Request(url, headers=headers), timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as problem:
            if problem.code not in (403, 429, 500, 502, 503) or attempt == attempts - 1:
                raise
            sleep(5 * 2**attempt)


def download_python(target: str, dest: Path) -> Path:
    url = find_python_asset(github_json(RELEASES, token=os.environ.get("GITHUB_TOKEN")), target)
    archive = dest / "python.tar.gz"
    with urllib.request.urlopen(url, timeout=600) as response, open(archive, "wb") as out:
        shutil.copyfileobj(response, out)
    with tarfile.open(archive) as t:
        t.extractall(dest)
    return dest / "python"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--os", required=True, choices=sorted(TARGETS))
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--version", required=True, help="MAJOR.MINOR.PATCH, as in the release tag without the v")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as tmp:
        python_dir = download_python(TARGETS[args.os], Path(tmp))
        interpreter = python_dir / ("python.exe" if args.os == "windows-x64" else "bin/python3")
        subprocess.run([str(interpreter), "-s", "-m", "pip", "install", "--no-warn-script-location", "-r", str(repo / "build" / "requirements.txt")], check=True)
        # the datasets of the zip: the big .xes from the data release, plus the csv made from the parquet the notebooks use
        datasets = Path(tmp) / "datasets"
        datasets.mkdir()
        for file in Path(args.data_dir).glob("*"):
            shutil.copy(file, datasets / file.name)
        export_csv(interpreter, repo / "notebooks" / "data" / "dhana-loan-application.parquet", datasets / "dhana-loan-application.csv")
        print(assemble(repo, python_dir, datasets, args.out, args.os, args.version))
    return 0


if __name__ == "__main__":
    sys.exit(main())
