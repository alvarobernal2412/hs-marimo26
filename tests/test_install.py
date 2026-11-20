"""The terminal installers (launcher/install.sh and install.ps1): a package fetched by a command, never by a browser, so the system
puts no "downloaded" mark on it. They are tried against a real package built by assemble(), given as a local file instead of a URL."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_build import BASH, ROOT, build_package, needs_bash

POWERSHELL = shutil.which("powershell") if sys.platform == "win32" else None
needs_powershell = pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell only")


def run_sh(zip_path, dest, arch="arm64"):
    env = {**os.environ, "HS_PACKAGE_URL": Path(zip_path).as_posix(), "HS_DEST": dest.as_posix(), "HS_ARCH": arch, "HS_NO_START": "1"}
    return subprocess.run([BASH, (ROOT / "launcher" / "install.sh").as_posix()], env=env, capture_output=True, text=True, timeout=120)


def run_ps1(zip_path, dest):
    env = {**os.environ, "HS_PACKAGE_URL": str(zip_path), "HS_DEST": str(dest), "HS_NO_START": "1"}
    command = [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "launcher" / "install.ps1")]
    return subprocess.run(command, env=env, capture_output=True, text=True, timeout=180)


@needs_bash
def test_install_sh_unpacks_the_mac_package_into_the_given_folder(tmp_path):
    package = build_package(tmp_path / "build", os_name="macos-arm64")
    dest = tmp_path / "my course" / "hs-marimo26"  # a space in the path, as a student's folder often has
    done = run_sh(package, dest)
    assert done.returncode == 0, done.stdout + done.stderr
    for name in ("Start.command", "Uninstall.command", "package-id.txt", "runtime.tar.gz", "launcher/start.py"):
        assert (dest / name).exists(), name
    assert subprocess.run([BASH, "-c", f'test -x "{(dest / "Start.command").as_posix()}"']).returncode == 0
    assert str(dest) in done.stdout or dest.as_posix() in done.stdout


@needs_bash
def test_install_sh_run_again_updates_the_package_and_keeps_the_other_files(tmp_path):
    dest = tmp_path / "hs-marimo26"
    assert run_sh(build_package(tmp_path / "one", os_name="macos-arm64", version="1.0.0"), dest).returncode == 0
    (dest / "my notes.txt").write_text("keep me")
    assert run_sh(build_package(tmp_path / "two", os_name="macos-arm64", version="1.1.0"), dest).returncode == 0
    assert (dest / "package-id.txt").read_text().strip() == "1.1.0"
    assert (dest / "my notes.txt").read_text() == "keep me"


@needs_bash
def test_install_sh_refuses_an_unknown_mac_type_and_creates_nothing(tmp_path):
    package = build_package(tmp_path / "build", os_name="macos-arm64")
    dest = tmp_path / "hs-marimo26"
    done = run_sh(package, dest, arch="ppc")
    assert done.returncode == 1
    assert "not supported" in done.stdout
    assert not dest.exists()


@needs_bash
def test_install_sh_says_so_and_creates_nothing_when_the_download_fails(tmp_path):
    dest = tmp_path / "hs-marimo26"
    done = run_sh(tmp_path / "no-such-file.zip", dest)
    assert done.returncode == 1
    assert "download did not work" in done.stdout
    assert not dest.exists()


@needs_powershell
def test_install_ps1_unpacks_the_windows_package_and_keeps_the_other_files(tmp_path):
    dest = tmp_path / "my course" / "hs-marimo26"
    done = run_ps1(build_package(tmp_path / "one", version="1.0.0"), dest)
    assert done.returncode == 0, done.stdout + done.stderr
    for name in ("Start.bat", "Uninstall.bat", "package-id.txt", "runtime.zip", "launcher/start.py"):
        assert (dest / name).exists(), name
    (dest / "my notes.txt").write_text("keep me")
    done = run_ps1(build_package(tmp_path / "two", version="1.1.0"), dest)
    assert done.returncode == 0, done.stdout + done.stderr
    assert (dest / "package-id.txt").read_text().strip() == "1.1.0"
    assert (dest / "my notes.txt").read_text() == "keep me"


@needs_powershell
def test_install_ps1_says_what_went_wrong_in_words_when_the_download_fails(tmp_path):
    dest = tmp_path / "hs-marimo26"
    done = run_ps1(tmp_path / "no-such-file.zip", dest)
    assert "Something went wrong" in done.stdout
    assert "photo of this window" in done.stdout


def test_the_release_publishes_the_install_scripts_next_to_the_zips():
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf8")
    assert "launcher/install.sh" in workflow and "launcher/install.ps1" in workflow
    assert "install.sh | bash" in workflow and "install.ps1 | iex" in workflow  # the lines students paste are in the release notes
