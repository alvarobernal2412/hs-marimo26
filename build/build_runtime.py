"""Builds the student zip of one operating system: Python 3.13 (python.org's signed embeddable build on Windows, python-build-standalone on
Mac) + pinned packages + launcher + notebooks + datasets.

Run it on the operating system it builds for (the packages are installed with that system's own pip):
    python build/build_runtime.py --os windows-x64 --data-dir DATA --out OUT --version 1.0.0
"""
from __future__ import annotations

import argparse
import io
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_notebooks_zip  # noqa: E402

TARGETS = {"windows-x64": "x86_64-pc-windows-msvc", "macos-arm64": "aarch64-apple-darwin", "macos-x64": "x86_64-apple-darwin"}
# the files a student double-clicks, at the root of the zip: start the notebooks, change the consent answer, remove everything
ROOT_SCRIPTS = {
    "windows-x64": ("Start.bat", "Change-my-answer.bat", "Uninstall.bat"),
    "macos-arm64": ("Start.command", "Change-my-answer.command", "Uninstall.command"),
    "macos-x64": ("Start.command", "Change-my-answer.command", "Uninstall.command"),
}
# the one big archive inside the zip, unpacked once by the system's own tar on the first start (a few files are quick to unzip;
# the tens of thousands inside are not, with Explorer's unzip)
RUNTIME_ARCHIVE = {"windows-x64": "runtime.zip", "macos-arm64": "runtime.tar.gz", "macos-x64": "runtime.tar.gz"}
RELEASES = "https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest"
PYTHON_ORG_FTP = "https://www.python.org/ftp/python"
GET_PIP = "https://bootstrap.pypa.io/get-pip.py"
# what the notebooks import (`provenance_widget` is the module of the marimo-pmprov package)
# The oldest macOS a Mac package must run on. pip on the build runner takes the newest wheel that runner's own macOS can use, so a
# package built on macOS 15 carried numpy and scipy built for macOS 14 and cvxopt built for macOS 15: a student's older Mac could
# not load them, and then no notebook starts. After the install, every package built for a newer macOS than this is installed
# again in its build for this one.
MAC_FLOOR = (12, 0)
MAC_ARCH = {"macos-arm64": "arm64", "macos-x64": "x86_64"}
# Packages left out of every package. cvxopt has no build for MAC_FLOOR, and pm4py uses it only when it is installed
# (pm4py/util/lp/solver.py) and solves with scipy otherwise: it is left out on Windows too, so that a student gets the same
# solver, and so the same results, on every system.
LEFT_OUT = ("cvxopt",)
SMOKE_MODULES = ("marimo", "pandas", "pyarrow", "altair", "vegafusion", "plotly", "networkx", "pm4py",
                 "provenance_widget.widget", "provenance_widget.sync")


def render_version_json(version: str) -> str:
    return json.dumps({"version": version})


def find_python_asset(release: dict, target: str) -> str:
    pattern = re.compile(rf"cpython-3\.13\.\d+\+\d+-{re.escape(target)}-install_only\.tar\.gz")
    for asset in release["assets"]:
        if pattern.fullmatch(asset["name"]):
            return asset["browser_download_url"]
    raise LookupError(f"no Python 3.13 build for {target}")


Entry = tuple[Path, str, int]  # (file on disk, name in the archive, unix mode)


def collect_runtime(repo: Path, python_dir: Path, data_dir: Path) -> list[Entry]:
    """What the first start unpacks into the runtime folder: python/, notebooks/ (with its data/), without bytecode caches."""
    entries: list[Entry] = []

    def add_tree(source: Path, prefix: str) -> None:
        for file in sorted(source.rglob("*")):
            if file.is_file() and "__pycache__" not in file.parts and file.suffix != ".pyc":
                relative = file.relative_to(source)
                executable = file.stat().st_mode & 0o111 or (prefix == "python" and relative.parts[0] == "bin")
                entries.append((file, f"{prefix}/{relative.as_posix()}", 0o755 if executable else 0o644))

    add_tree(python_dir, "python")
    add_tree(repo / "notebooks", "notebooks")
    for file in sorted(Path(data_dir).glob("*")):
        entries.append((file, f"notebooks/data/{file.name}", 0o644))
    return entries


def write_runtime_archive(entries: list[Entry], version: str, dest: Path) -> None:
    """`runtime.zip` or `runtime.tar.gz` (by the name of `dest`) of the entries plus `version.json`; the first entry of a name wins."""
    seen: set[str] = set()
    unique = [entry for entry in entries if not (entry[1] in seen or seen.add(entry[1]))]
    version_json = render_version_json(version).encode("utf8")
    if dest.suffix == ".zip":
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            for file, name, mode in unique:
                add_to_zip(z, file, name, mode, zipfile.ZIP_DEFLATED)
            z.writestr("version.json", version_json)
        return
    with tarfile.open(dest, "w:gz") as t:  # a tar keeps executable bits and symlinks, which zip handles badly on a Mac
        for file, name, mode in unique:
            info = t.gettarinfo(str(file), arcname=name)
            info.mode, info.uid, info.gid, info.uname, info.gname = mode, 0, 0, "", ""
            with open(file, "rb") as src:
                t.addfile(info, src)
        info = tarfile.TarInfo("version.json")
        info.size, info.mode = len(version_json), 0o644
        t.addfile(info, io.BytesIO(version_json))


def add_to_zip(z: zipfile.ZipFile, file: Path, name: str, mode: int, compress_type: int) -> None:
    info = zipfile.ZipInfo.from_file(file, name)
    info.external_attr = (mode | 0o100000) << 16
    info.compress_type = compress_type
    with open(file, "rb") as src, z.open(info, "w", force_zip64=True) as dst:
        shutil.copyfileobj(src, dst, 1024 * 1024)


def assemble(repo: Path, python_dir: Path, data_dir: Path, out_dir: Path, os_name: str, version: str, build_id: str = "") -> Path:
    """Builds the student zip: a few loose files plus ONE runtime archive; returns the zip's path.

    `package-id.txt` says which build this is: the version, plus `-<build_id>` when there is one. A computer that already unpacked a
    package with that id does not unpack it again, so a version published again (the same number, new contents) needs a new id to
    reach it. The runtime's own `version.json` keeps the plain version, which is what the updater compares."""
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"hs-marimo26-v{version}-{os_name}.zip"
    with tempfile.TemporaryDirectory() as tmp:
        runtime = Path(tmp) / RUNTIME_ARCHIVE[os_name]
        # what the updater compares a later release with: the notebook files of this one, and the libraries it installs
        listed = Path(tmp) / "manifest.json"
        listed.write_text(json.dumps(make_notebooks_zip.manifest(repo / "notebooks", repo / "build" / "requirements.txt")), encoding="utf8")
        entries = collect_runtime(repo, python_dir, data_dir) + [(listed, "manifest.json", 0o644)]
        write_runtime_archive(entries, version, runtime)
        package_id = Path(tmp) / "package-id.txt"
        package_id.write_text((f"{version}-{build_id}" if build_id else version) + "\n", encoding="utf8")
        launcher = repo / "launcher"
        loose: list[Entry] = [(launcher / script, script, 0o755) for script in ROOT_SCRIPTS[os_name]]
        loose += [(launcher / name, f"launcher/{name}", 0o644) for name in ("start.py", "update.py", "consent.py", "notice.py")]
        loose.append((launcher / "START-HERE.txt", "START-HERE.txt", 0o644))
        loose.append((package_id, "package-id.txt", 0o644))
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for file, name, mode in loose:
                add_to_zip(z, file, name, mode, zipfile.ZIP_DEFLATED)
            add_to_zip(z, runtime, runtime.name, 0o644, zipfile.ZIP_STORED)  # already compressed
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


def find_python_org_embed(exists, newest_patch: int = 30) -> tuple[str, str]:
    """The newest Python 3.13.x with a Windows embeddable zip on python.org, as (version, url). The newest patch releases are often
    source-only, so this walks down from `newest_patch` until `exists(url)` says the zip is there."""
    for patch in range(newest_patch, -1, -1):
        version = f"3.13.{patch}"
        url = f"{PYTHON_ORG_FTP}/{version}/python-{version}-embed-amd64.zip"
        if exists(url):
            return version, url
    raise LookupError("no Windows embeddable Python 3.13 on python.org")


def url_exists(url: str) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers={"User-Agent": "hs-marimo26"}), timeout=60):
            return True
    except urllib.error.HTTPError as problem:
        if problem.code == 404:
            return False
        raise


def write_embed_pth(python_dir: Path) -> Path:
    """The embeddable Python ignores site-packages unless its `._pth` file names them and enables `site`."""
    pth = next(Path(python_dir).glob("python*._pth"))
    pth.write_text(f"{pth.stem}.zip\n.\nLib\\site-packages\nimport site\n", encoding="utf8")
    return pth


def download_python_org(dest: Path) -> Path:
    """Windows: python.org's own embeddable Python. Its python.exe is signed by the Python Software Foundation; the standalone build's
    is not, and a university's Defender policy ("Access is denied") blocks an unsigned, never-seen executable from starting."""
    version, url = find_python_org_embed(url_exists)
    print(f"Using python.org Python {version}")
    archive = dest / "embed.zip"
    with urllib.request.urlopen(url, timeout=600) as response, open(archive, "wb") as out:
        shutil.copyfileobj(response, out)
    python_dir = dest / "python"
    with zipfile.ZipFile(archive) as z:
        z.extractall(python_dir)
    write_embed_pth(python_dir)
    get_pip = dest / "get-pip.py"  # the embeddable Python has no pip
    with urllib.request.urlopen(GET_PIP, timeout=120) as response, open(get_pip, "wb") as out:
        shutil.copyfileobj(response, out)
    subprocess.run([str(python_dir / "python.exe"), str(get_pip), "--no-warn-script-location"], check=True)
    return python_dir


def download_standalone(target: str, dest: Path) -> Path:
    url = find_python_asset(github_json(RELEASES, token=os.environ.get("GITHUB_TOKEN")), target)
    archive = dest / "python.tar.gz"
    with urllib.request.urlopen(url, timeout=600) as response, open(archive, "wb") as out:
        shutil.copyfileobj(response, out)
    with tarfile.open(archive) as t:
        t.extractall(dest)
    return dest / "python"


def download_python(target: str, dest: Path) -> Path:
    if target == TARGETS["windows-x64"]:
        return download_python_org(dest)
    return download_standalone(target, dest)


def wheel_macos_version(wheel_text: str) -> tuple[int, int] | None:
    """The macOS a wheel was built for, from the `Tag:` lines of its WHEEL file: the oldest of them when it has several (any one
    of them is enough to run it). None for a wheel that is not built for a macOS (pure Python)."""
    found = [(int(major), int(minor)) for major, minor in re.findall(r"^Tag:.*-macosx_(\d+)_(\d+)_", wheel_text, flags=re.MULTILINE)]
    return min(found) if found else None


def built_for_newer_macos(site_packages: Path, floor: tuple[int, int] = MAC_FLOOR) -> list[tuple[str, str, tuple[int, int]]]:
    """The installed packages built for a newer macOS than `floor`, as (name, version, that macOS)."""
    newer = []
    for wheel in sorted(Path(site_packages).glob("*.dist-info/WHEEL")):
        needs = wheel_macos_version(wheel.read_text(encoding="utf8"))
        if needs is None or needs <= floor:
            continue
        metadata = (wheel.parent / "METADATA").read_text(encoding="utf8")
        name = re.search(r"^Name: *(.+)$", metadata, flags=re.MULTILINE)[1].strip()
        version = re.search(r"^Version: *(.+)$", metadata, flags=re.MULTILINE)[1].strip()
        newer.append((name, version, needs))
    return newer


def leave_out(interpreter: Path, names: tuple[str, ...] = LEFT_OUT, run=subprocess.run) -> None:
    """Removes the packages of LEFT_OUT, which pip installed because another package asks for them."""
    for name in names:
        print(f"leaving {name} out of the package", flush=True)
        run([str(interpreter), "-s", "-m", "pip", "uninstall", "--yes", name], check=True)


def retarget_for_older_macs(interpreter: Path, site_packages: Path, os_name: str, run=subprocess.run) -> None:
    """Replaces every package built for a newer macOS than MAC_FLOOR by the same version built for MAC_FLOOR (or older). Stops the
    build when a package is still too new afterwards (it has no such build), so it never reaches a student."""
    platform = f"macosx_{MAC_FLOOR[0]}_{MAC_FLOOR[1]}_{MAC_ARCH[os_name]}"
    pip = [str(interpreter), "-s", "-m", "pip"]
    for name, version, needs in built_for_newer_macos(site_packages):
        print(f"{name} {version} was built for macOS {needs[0]}.{needs[1]}: installing its build for macOS {MAC_FLOOR[0]}.{MAC_FLOOR[1]}",
              flush=True)
        run([*pip, "uninstall", "--yes", name], check=True)
        # --platform also accepts the wheels of every older macOS; it needs --target, and no dependencies (they are installed)
        run([*pip, "install", "--no-warn-script-location", "--no-deps", "--only-binary=:all:", "--platform", platform,
             "--target", str(site_packages), f"{name}=={version}"], check=True)
    still = built_for_newer_macos(site_packages)
    if still:
        raise SystemExit(f"built for a newer macOS than {MAC_FLOOR[0]}.{MAC_FLOOR[1]}: " + ", ".join(f"{n} {v}" for n, v, _ in still))


def smoke_test(interpreter: Path, modules: tuple[str, ...] = SMOKE_MODULES) -> None:
    """Starts the built Python and imports what the notebooks need, so a broken runtime fails the build, not a student's first start."""
    subprocess.run([str(interpreter), "-s", "-c", "import " + ", ".join(modules)], check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--os", required=True, choices=sorted(TARGETS))
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--version", required=True, help="MAJOR.MINOR.PATCH, as in the release tag without the v")
    parser.add_argument("--build-id", default="", help="what tells this build from another of the same version, such as a commit's first 7 characters")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as tmp:
        python_dir = download_python(TARGETS[args.os], Path(tmp))
        interpreter = python_dir / ("python.exe" if args.os == "windows-x64" else "bin/python3")
        subprocess.run([str(interpreter), "-s", "-m", "pip", "install", "--no-warn-script-location", "-r", str(repo / "build" / "requirements.txt")], check=True)
        leave_out(interpreter)
        if args.os in MAC_ARCH:
            retarget_for_older_macs(interpreter, next((python_dir / "lib").glob("python3.*/site-packages")), args.os)
        smoke_test(interpreter)
        # the datasets of the zip: the big .xes from the data release, plus the csv made from the parquet the notebooks use
        datasets = Path(tmp) / "datasets"
        datasets.mkdir()
        for file in Path(args.data_dir).glob("*"):
            shutil.copy(file, datasets / file.name)
        export_csv(interpreter, repo / "notebooks" / "data" / "dhana-loan-application.parquet", datasets / "dhana-loan-application.csv")
        print(assemble(repo, python_dir, datasets, args.out, args.os, args.version, args.build_id))
    return 0


if __name__ == "__main__":
    sys.exit(main())
