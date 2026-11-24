"""Puts a copy of marimo-pmprov (the module `provenance_widget`) into `notebooks/vendor/`, which the notebooks import before the
installed one.

The student package installs its libraries once; a start only brings the `notebooks/` folder up to date. marimo-pmprov is plain
files (Python, one script, a stylesheet, fonts), so a copy of it among the notebooks reaches every student with the next start,
without a new package. Use it for a version of marimo-pmprov that needs no library the package lacks: when `build/requirements.txt`
has to change, that is a new MAJOR (see the README).

    python build/vendor_library.py --wheel marimo_pmprov-0.16.0-py3-none-any.whl     # a released wheel (pip download marimo-pmprov==0.16.0 --no-deps)
    python build/vendor_library.py --checkout ../marimo-pmprov                       # a checkout, as it is on disk

`notebooks/vendor/VENDORED.json` says what is there: the version, where it came from and a hash of the files, which
tests/test_vendored_library.py checks, so the copy is never edited by hand.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

MODULE = "provenance_widget"
VENDOR = Path(__file__).resolve().parents[1] / "notebooks" / "vendor"
RECORD = "VENDORED.json"
SKIP = {"__pycache__"}


def module_files(folder: Path) -> list[Path]:
    """The files of a module folder that are shipped: no bytecode caches, no placeholders."""
    return sorted(
        f for f in Path(folder).rglob("*")
        if f.is_file() and not SKIP & set(f.relative_to(folder).parts) and f.suffix != ".pyc" and f.name != ".gitkeep"
    )


def tree_hash(folder: Path) -> str:
    """One hash of the files of a module folder: their names and contents. Line endings do not count for text, so a checkout on
    Windows and one on a Mac give the same."""
    digest = hashlib.sha256()
    for file in module_files(folder):
        data = file.read_bytes()
        if file.suffix in {".py", ".js", ".css", ".txt", ".json"}:
            data = data.replace(b"\r\n", b"\n")
        digest.update(file.relative_to(folder).as_posix().encode("utf8") + b"\0" + hashlib.sha256(data).digest())
    return digest.hexdigest()


def version_of_checkout(checkout: Path) -> str:
    found = re.search(r'^version\s*=\s*"([^"]+)"', (Path(checkout) / "pyproject.toml").read_text(encoding="utf8"), re.MULTILINE)
    if not found:
        raise SystemExit(f"no version in {checkout}/pyproject.toml")
    return found[1]


def state_of_checkout(checkout: Path) -> str:
    """What a checkout is at, for the record: its tag when it is at one (`v0.16.0`), else its commit; "-dirty" when files differ."""
    try:
        told = subprocess.run(
            ["git", "-C", str(checkout), "describe", "--tags", "--always", "--dirty"], capture_output=True, text=True, check=True
        )
        return told.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return Path(checkout).resolve().name


def vendor(source: Path, version: str, origin: str, vendor_dir: Path = VENDOR) -> dict:
    """Replace `vendor_dir/provenance_widget` by the module folder `source` and write the record. Returns the record."""
    if not (Path(source) / "__init__.py").is_file() or not (Path(source) / "static" / "widget.js").is_file():
        raise SystemExit(f"{source} is not a built provenance_widget (no __init__.py or no static/widget.js)")
    target = Path(vendor_dir) / MODULE
    if target.exists():
        shutil.rmtree(target)
    for file in module_files(source):
        copy = target / file.relative_to(source)
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, copy)
    record = {"package": "marimo-pmprov", "module": MODULE, "version": version, "from": origin, "sha256": tree_hash(target)}
    (Path(vendor_dir) / RECORD).write_text(json.dumps(record, indent=1) + "\n", encoding="utf8")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--wheel", type=Path, help="a marimo_pmprov-<version>-*.whl file")
    where.add_argument("--checkout", type=Path, help="a checkout of marimo-pmprov, with its frontend built")
    args = parser.parse_args(argv)
    if args.wheel:
        found = re.match(r"marimo_pmprov-([^-]+)-", args.wheel.name)
        if not found:
            raise SystemExit(f"{args.wheel.name} is not a marimo-pmprov wheel")
        with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(args.wheel) as wheel:
            wheel.extractall(tmp)
            record = vendor(Path(tmp) / MODULE, found[1], f"wheel {args.wheel.name}")
    else:
        record = vendor(args.checkout / MODULE, version_of_checkout(args.checkout), f"checkout at {state_of_checkout(args.checkout)}")
    print(f"notebooks/vendor/{MODULE}: marimo-pmprov {record['version']} ({record['from']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
