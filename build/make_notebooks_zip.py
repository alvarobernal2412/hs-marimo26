"""Zips the notebooks folder for a `notebooks-N` release: without the big `.xes` logs, caches and anything a student produced."""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

SKIP_DIRS = {"__pycache__", "provenance"}


def make_zip(notebooks: Path, out: Path) -> None:
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for file in sorted(Path(notebooks).rglob("*")):
            relative = file.relative_to(notebooks)
            if not file.is_file() or SKIP_DIRS & set(relative.parts) or file.suffix in {".xes", ".pyc"}:
                continue
            z.write(file, relative.as_posix())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    make_zip(Path(__file__).resolve().parents[1] / "notebooks", args.out)
    sys.exit(0)
