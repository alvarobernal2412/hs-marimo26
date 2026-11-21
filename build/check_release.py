"""Refuses to build a release that changes the libraries without a new MAJOR version.

A student's launcher brings new notebooks by itself, but libraries only arrive with a new package, which the student gets by
pasting the install line again; the launcher asks for that when the MAJOR number grew. So a change in `build/requirements.txt`
has to come with a new MAJOR. (A launcher that meets such notebooks anyway does not apply them, see launcher/update.py: this
check is what tells the person releasing, before any student is affected.)

    python build/check_release.py --version 1.3.0
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "launcher"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_notebooks_zip  # noqa: E402
import update  # noqa: E402

Published = tuple[update.Version, str | None]


def published(find=update.latest_release, download=update.download_to) -> Published | None:
    """The release students have now, as (version, hash of its libraries or None when it does not say); None when there is none."""
    release = find()
    if not release:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "notebooks.zip"
        download(release["zip_url"], archive)
        with zipfile.ZipFile(archive) as z:
            listed = update.read_manifest(z.read(update.MANIFEST)) if update.MANIFEST in z.namelist() else {}
    return release["version"], listed.get("requirements")


def problem(previous: Published | None, version: update.Version, requirements: str) -> str | None:
    """Why `version` cannot be released with these libraries, or None when it can."""
    if previous is None:
        return None
    before, libraries = previous
    if libraries is None or libraries == requirements or version[0] != before[0] or version <= before:
        return None
    return (
        f"build/requirements.txt changed since v{'.'.join(map(str, before))}, which students have now. Their launchers cannot bring "
        f"libraries, only notebooks, so this has to be a new package: release it as {before[0] + 1}.0.0."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True, help="MAJOR.MINOR.PATCH of the release being built")
    args = parser.parse_args()
    wanted = update.parse_version(args.version)
    if wanted is None:
        sys.exit(f"{args.version} is not MAJOR.MINOR.PATCH")
    found = problem(published(), wanted, make_notebooks_zip.requirements_hash(make_notebooks_zip.REQUIREMENTS))
    if found:
        sys.exit(found)
    print("The libraries match what this version number promises.")
