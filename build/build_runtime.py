"""Builds the student zip of one operating system: standalone Python 3.13 + pinned packages + launcher + notebooks + datasets.

Run it on the operating system it builds for (the packages are installed with that system's own pip):
    python build/build_runtime.py --os windows-x64 --data-dir DATA --out OUT [--runtime 1] [--notebooks 1]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

TARGETS = {"windows-x64": "x86_64-pc-windows-msvc", "macos-arm64": "aarch64-apple-darwin", "macos-x64": "x86_64-apple-darwin"}
LAUNCHER_AT_ROOT = {"windows-x64": "Start.bat", "macos-arm64": "Start.command", "macos-x64": "Start.command"}
RELEASES = "https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest"


def render_version_json(runtime: int, notebooks: int) -> str:
    return json.dumps({"runtime": runtime, "notebooks": notebooks})


def find_python_asset(release: dict, target: str) -> str:
    pattern = re.compile(rf"cpython-3\.13\.\d+\+\d+-{re.escape(target)}-install_only\.tar\.gz")
    for asset in release["assets"]:
        if pattern.fullmatch(asset["name"]):
            return asset["browser_download_url"]
    raise LookupError(f"no Python 3.13 build for {target}")


def assemble(repo: Path, python_dir: Path, data_dir: Path, out_dir: Path, os_name: str, runtime: int, notebooks: int) -> Path:
    """Lays the bundle out and zips it; returns the zip's path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"hs-marimo26-{os_name}-runtime{runtime}.zip"
    entries: list[tuple[Path, str, int]] = []  # (file, name in zip, unix mode)

    def add_tree(source: Path, prefix: str) -> None:
        for file in sorted(source.rglob("*")):
            if file.is_file() and "__pycache__" not in file.parts and file.suffix != ".pyc":
                executable = file.stat().st_mode & 0o111 or prefix == "python/bin"
                entries.append((file, f"{prefix}/{file.relative_to(source).as_posix()}", 0o755 if executable else 0o644))

    add_tree(python_dir, "python")
    add_tree(repo / "notebooks", "notebooks")
    for name in ("start.py", "update.py"):
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
        z.writestr("version.json", render_version_json(runtime, notebooks))
    return zip_path


def download_python(target: str, dest: Path) -> Path:
    with urllib.request.urlopen(urllib.request.Request(RELEASES, headers={"User-Agent": "hs-marimo26"}), timeout=60) as response:
        url = find_python_asset(json.load(response), target)
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
    parser.add_argument("--runtime", type=int, default=1)
    parser.add_argument("--notebooks", type=int, default=1)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as tmp:
        python_dir = download_python(TARGETS[args.os], Path(tmp))
        interpreter = python_dir / ("python.exe" if args.os == "windows-x64" else "bin/python3")
        subprocess.run([str(interpreter), "-s", "-m", "pip", "install", "--no-warn-script-location", "-r", str(repo / "build" / "requirements.txt")], check=True)
        print(assemble(repo, python_dir, args.data_dir, args.out, args.os, args.runtime, args.notebooks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
