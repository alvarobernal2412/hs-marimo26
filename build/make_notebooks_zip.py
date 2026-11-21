"""Zips the notebooks folder for a release: without the big `.xes` logs, caches and anything a student produced."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

SKIP_DIRS = {"__pycache__", "provenance"}


REQUIREMENTS = Path(__file__).resolve().parent / "requirements.txt"


def shipped_files(notebooks: Path) -> list[tuple[Path, str]]:
    """The notebook files a release ships, as (file, name in the zip)."""
    found = []
    for file in sorted(Path(notebooks).rglob("*")):
        relative = file.relative_to(notebooks)
        if not file.is_file() or SKIP_DIRS & set(relative.parts) or file.suffix in {".xes", ".pyc"}:
            continue
        found.append((file, relative.as_posix()))
    return found


def requirements_hash(requirements: Path) -> str:
    """A hash of the libraries the package installs: the lines that name one, whatever their order."""
    lines = (line.split("#", 1)[0].strip() for line in Path(requirements).read_text(encoding="utf8").splitlines())
    return hashlib.sha256("\n".join(sorted(line for line in lines if line)).encode("utf8")).hexdigest()


def manifest(notebooks: Path, requirements: Path | None = None) -> dict:
    """What the launcher's updater compares (see launcher/update.py): the files this release ships, so that a later release can
    remove the ones it dropped, and the libraries they were made for, so that they are never put on a package that lacks them."""
    found: dict = {"files": [name for _, name in shipped_files(notebooks)]}
    if requirements is not None:
        found["requirements"] = requirements_hash(requirements)
    return found


def make_zip(notebooks: Path, out: Path, requirements: Path | None = None) -> None:
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for file, name in shipped_files(notebooks):
            z.write(file, name)
        z.writestr("manifest.json", json.dumps(manifest(notebooks, requirements)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    make_zip(Path(__file__).resolve().parents[1] / "notebooks", args.out, REQUIREMENTS)
    sys.exit(0)
