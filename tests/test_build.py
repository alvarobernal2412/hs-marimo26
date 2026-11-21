import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import build_runtime as br  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_render_version_json():
    assert json.loads(br.render_version_json("1.2.3")) == {"version": "1.2.3"}


def test_find_python_asset_picks_install_only_for_target():
    release = {"assets": [
        {"name": "cpython-3.13.1+20250101-x86_64-pc-windows-msvc-install_only_stripped.tar.gz", "browser_download_url": "stripped"},
        {"name": "cpython-3.13.1+20250101-x86_64-pc-windows-msvc-install_only.tar.gz", "browser_download_url": "win"},
        {"name": "cpython-3.12.8+20250101-x86_64-pc-windows-msvc-install_only.tar.gz", "browser_download_url": "old"},
        {"name": "cpython-3.13.1+20250101-aarch64-apple-darwin-install_only.tar.gz", "browser_download_url": "mac"},
    ]}
    assert br.find_python_asset(release, "x86_64-pc-windows-msvc") == "win"
    assert br.find_python_asset(release, "aarch64-apple-darwin") == "mac"


def build_package(tmp_path, os_name="windows-x64", version="1.2.3", build_id=""):
    """A tiny fake runtime run through the real assemble(); returns the outer zip's path."""
    python_dir = tmp_path / "py"
    (python_dir / "bin").mkdir(parents=True)
    (python_dir / "python.exe").write_text("")
    (python_dir / "bin" / "python3").write_text("")
    (python_dir / "bin" / "python3").chmod(0o755)
    (python_dir / "pkg" / "__pycache__").mkdir(parents=True)
    (python_dir / "pkg" / "__pycache__" / "x.cpython-313.pyc").write_text("")
    data = tmp_path / "data"
    data.mkdir()
    (data / "dhana-loan-application-molab.xes").write_text("X")
    return br.assemble(ROOT, python_dir, data, tmp_path / "out", os_name=os_name, version=version, build_id=build_id)


def inner_zip(outer_path: Path, name: str = "runtime.zip") -> zipfile.ZipFile:
    import io

    with zipfile.ZipFile(outer_path) as outer:
        return zipfile.ZipFile(io.BytesIO(outer.read(name)))


def test_outer_zip_has_only_the_expected_entries(tmp_path):
    zip_path = build_package(tmp_path)
    assert zip_path.name == "hs-marimo26-v1.2.3-windows-x64.zip"
    with zipfile.ZipFile(zip_path) as z:
        assert set(z.namelist()) == {
            "Start.bat", "Change-my-answer.bat", "Uninstall.bat", "START-HERE.txt", "package-id.txt", "runtime.zip",
            "launcher/start.py", "launcher/update.py", "launcher/consent.py",
        }


def test_the_runtime_lists_the_notebook_files_it_ships_and_the_libraries_they_were_made_for(tmp_path):
    import make_notebooks_zip as mz

    found = json.loads(inner_zip(build_package(tmp_path)).read("manifest.json"))
    assert "00_lecture.py" in found["files"] and "lib/initial_analysis_kit.py" in found["files"]
    assert not any(name.endswith(".xes") or name == "manifest.json" for name in found["files"])
    assert found["requirements"] == mz.requirements_hash(ROOT / "build" / "requirements.txt")
    mz.make_zip(ROOT / "notebooks", tmp_path / "notebooks.zip", ROOT / "build" / "requirements.txt")
    assert json.loads(zipfile.ZipFile(tmp_path / "notebooks.zip").read("manifest.json")) == found  # an update compares the two


def test_package_id_is_the_version(tmp_path):
    with zipfile.ZipFile(build_package(tmp_path)) as z:
        assert z.read("package-id.txt").decode("utf8").strip() == "1.2.3"


def test_runtime_zip_holds_python_notebooks_and_version(tmp_path):
    names = set(inner_zip(build_package(tmp_path)).namelist())
    for expected in ("python/python.exe", "notebooks/00_lecture.py", "notebooks/data/dhana-loan-application-molab.xes", "version.json"):
        assert expected in names, expected
    assert not any(name.startswith("launcher/") for name in names)
    assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)


def test_runtime_is_stored_not_recompressed(tmp_path):
    with zipfile.ZipFile(build_package(tmp_path)) as z:
        assert z.getinfo("runtime.zip").compress_type == zipfile.ZIP_STORED


def test_mac_runtime_is_a_tar_that_keeps_exec_bits(tmp_path):
    import io
    import tarfile

    with zipfile.ZipFile(build_package(tmp_path, os_name="macos-arm64")) as z:
        names = set(z.namelist())
        archive = z.read("runtime.tar.gz")
    assert {"Start.command", "Change-my-answer.command", "runtime.tar.gz"} <= names
    assert not any(name.endswith(".bat") for name in names)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as t:
        assert t.getmember("python/bin/python3").mode & 0o777 == 0o755
        assert t.getmember("notebooks/00_lecture.py").mode & 0o777 == 0o644
        assert "version.json" in t.getnames()


def test_system_tar_unpacks_the_windows_runtime(tmp_path):
    import shutil
    import subprocess

    import pytest

    if shutil.which("tar") is None:
        pytest.skip("no tar on this machine")
    zip_path = build_package(tmp_path)
    outer = tmp_path / "outer"
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    with zipfile.ZipFile(zip_path) as z:
        z.extract("runtime.zip", outer)
    subprocess.run(["tar", "-xf", str(outer / "runtime.zip"), "-C", str(runtime)], check=True)
    assert (runtime / "python" / "python.exe").exists()
    assert (runtime / "version.json").exists()


def test_export_csv_writes_the_log_with_its_columns(tmp_path):
    import pandas as pd

    parquet = tmp_path / "log.parquet"
    pd.DataFrame({"case_concept_name": ["A1", "A2"], "concept_name": ["x", "y"]}).to_parquet(parquet)
    out = tmp_path / "log.csv"
    br.export_csv(Path(sys.executable), parquet, out)
    assert out.read_text(encoding="utf8").splitlines() == ["case_concept_name,concept_name", "A1,x", "A2,y"]


def test_github_json_sends_the_token_and_retries_when_rate_limited():
    import io
    import urllib.error

    calls, headers_seen = [], []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def opener(request, timeout=None):
        calls.append(request.full_url)
        headers_seen.append(request.get_header("Authorization"))
        if len(calls) < 3:
            raise urllib.error.HTTPError(request.full_url, 403, "rate limit exceeded", {}, None)
        return Response(b'{"ok": true}')

    result = br.github_json("https://api.github.com/x", token="secret", sleep=lambda seconds: None, opener=opener)

    assert result == {"ok": True} and len(calls) == 3
    assert headers_seen == ["Bearer secret"] * 3


def test_github_json_gives_up_after_the_attempts_and_does_not_retry_other_errors():
    import urllib.error

    def always_limited(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 403, "rate limit exceeded", {}, None)

    with pytest.raises(urllib.error.HTTPError):
        br.github_json("https://api.github.com/x", attempts=2, sleep=lambda seconds: None, opener=always_limited)

    calls = []

    def not_found(request, timeout=None):
        calls.append(1)
        raise urllib.error.HTTPError(request.full_url, 404, "not found", {}, None)

    with pytest.raises(urllib.error.HTTPError):
        br.github_json("https://api.github.com/x", sleep=lambda seconds: None, opener=not_found)
    assert calls == [1]  # a 404 is not worth retrying


def test_start_bat_unpacks_once_with_tar_and_passes_flags():
    text = (ROOT / "launcher" / "Start.bat").read_text(encoding="utf8")
    for expected in (r"%LOCALAPPDATA%\hs-marimo26\runtime", "package-id.txt", "ready-!PKG!", r"System32\tar.exe", "Expand-Archive", "%*"):
        assert expected in text, expected  # System32's tar reads zip; a Git-for-Windows tar earlier on the PATH does not
    assert "enabledelayedexpansion" in text  # a path with ")" in it must not close the batch block
    # an interrupted setup must be safe to repeat: unpack next to the runtime, mark it complete INSIDE the new folder, and only then
    # swap it in; a leftover half-unpacked folder is thrown away, a complete one is only swapped
    assert "!RT!.new" in text and r"python\python.exe" in text
    assert text.index("rmdir /s /q \"!NEW!\"") < text.index("-xf") < text.index("type nul") < text.index("move ")


def test_change_my_answer_scripts_call_start_with_consent():
    bat = (ROOT / "launcher" / "Change-my-answer.bat").read_text(encoding="utf8")
    command = (ROOT / "launcher" / "Change-my-answer.command").read_text(encoding="utf8")
    assert 'Start.bat" --consent' in bat
    assert 'Start.command" --consent' in command
    assert command.startswith("#!/bin/bash")


def test_student_readme_installs_with_one_pasted_line_and_has_no_flags():
    text = (ROOT / "launcher" / "START-HERE.txt").read_text(encoding="utf8")
    assert "Change-my-answer" in text and "--consent" not in text
    assert "install.sh | bash" in text and "install.ps1 | iex" in text  # the one line each system pastes, once
    assert "Open Anyway" not in text and "Extract All" not in text  # no browser download any more: no security dialog, no unzipping
    assert "Documents" not in text  # the zip is small now and unpacks itself elsewhere; no folder advice that points into OneDrive


def test_python_org_embed_picks_the_newest_patch_that_has_windows_binaries():
    asked = []

    def exists(url):
        asked.append(url)
        return "3.13.17" in url

    version, url = br.find_python_org_embed(exists, newest_patch=19)
    assert version == "3.13.17"
    assert url == "https://www.python.org/ftp/python/3.13.17/python-3.13.17-embed-amd64.zip"
    assert [u.split("/")[5] for u in asked] == ["3.13.19", "3.13.18", "3.13.17"]  # newest first, stops at the first hit


def test_python_org_embed_gives_up_when_no_patch_has_binaries():
    with pytest.raises(LookupError):
        br.find_python_org_embed(lambda url: False, newest_patch=3)


def test_embed_pth_names_site_packages_and_enables_site(tmp_path):
    (tmp_path / "python314._pth").write_text("python314.zip\n.\n#import site\n")
    br.write_embed_pth(tmp_path)
    assert (tmp_path / "python314._pth").read_text().splitlines() == ["python314.zip", ".", r"Lib\site-packages", "import site"]


def test_windows_build_uses_the_signed_python_org_python_and_the_others_the_standalone(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(br, "download_python_org", lambda dest: calls.append("python.org") or dest / "python")
    monkeypatch.setattr(br, "download_standalone", lambda target, dest: calls.append(target) or dest / "python")
    br.download_python(br.TARGETS["windows-x64"], tmp_path)
    br.download_python(br.TARGETS["macos-arm64"], tmp_path)
    assert calls == ["python.org", "aarch64-apple-darwin"]


def test_smoke_test_passes_for_importable_modules_and_fails_for_missing_ones():
    import subprocess

    br.smoke_test(Path(sys.executable), modules=("json", "zipfile"))
    with pytest.raises(subprocess.CalledProcessError):
        br.smoke_test(Path(sys.executable), modules=("no_such_module_for_the_smoke_test",))


def test_start_here_explains_stopping_sleeping_and_restarting():
    text = (ROOT / "launcher" / "START-HERE.txt").read_text(encoding="utf8")
    for expected in ("STOPPING, AND STARTING AGAIN", "SLEEP", "SHUTS DOWN", "nothing keeps running in the background",
                     "double-click Start again", "finishes the setup"):
        assert expected in text, expected


def test_student_readme_explains_how_to_open_a_terminal_and_the_managed_laptop_block():
    text = (ROOT / "launcher" / "START-HERE.txt").read_text(encoding="utf8")
    assert "Terminal" in text and "PowerShell" in text  # where to paste the line, for a student who never saw one
    assert "IT department" in text  # a university-managed laptop may need its IT team to allow the folder


def test_start_command_unpacks_once_with_tar_and_passes_flags():
    text = (ROOT / "launcher" / "Start.command").read_text(encoding="utf8")
    for expected in ("Library/Application Support/hs-marimo26/runtime", "package-id.txt", "ready-", "/usr/bin/tar -xzf", '"$@"'):
        assert expected in text, expected
    assert '"$RT.new"' in text and "python/bin/python3" in text  # unpacked beside the runtime, swapped in only when complete
    assert text.index("rm -rf \"$NEW\"") < text.index("/usr/bin/tar -xzf") < text.index("touch ") < text.index("mv ")

# --- Start.command on a Mac, run for real with bash ----------------------------------------------------------------------------------
def find_bash():
    """A bash that understands this machine's paths: on Windows Git's (the bash on the PATH there can be WSL's, which does not)."""
    if sys.platform == "win32":
        git = shutil.which("git")
        for folder in Path(git).parents if git else []:  # git sits at Git\\cmd, Git\\bin or Git\\mingw64\\bin: look up from there
            for relative in ("bin/bash.exe", "usr/bin/bash.exe"):
                if (folder / relative).exists():
                    return str(folder / relative)
        return None
    return shutil.which("bash")


BASH = find_bash()
needs_bash = pytest.mark.skipif(BASH is None, reason="no usable bash on this machine")


def test_start_command_sets_up_once_and_a_second_start_needs_no_archive(tmp_path):
    import tarfile

    package = tmp_path / "course tools"  # a space in the name, as a student's folder often has
    package.mkdir()
    shutil.copy(ROOT / "launcher" / "Start.command", package / "Start.command")
    (package / "package-id.txt").write_text("1.2.3\n")
    python = tmp_path / "rt" / "python" / "bin"
    python.mkdir(parents=True)
    (python / "python3").write_text("#!/bin/sh\n")
    (python / "python3").chmod(0o755)
    with tarfile.open(package / "runtime.tar.gz", "w:gz") as t:
        t.add(tmp_path / "rt" / "python", arcname="python")
    home = tmp_path / "home"
    home.mkdir()
    env = {**os.environ, "HOME": home.as_posix(), "HS_SETUP_ONLY": "1"}

    def start():
        done = subprocess.run([BASH, (package / "Start.command").as_posix()], env=env, capture_output=True, text=True, timeout=120)
        assert done.returncode == 0, done.stdout + done.stderr

    start()
    support = home / "Library" / "Application Support" / "hs-marimo26"
    assert (support / "runtime" / "ready-1.2.3").exists() and (support / "runtime" / "python" / "bin" / "python3").exists()
    assert not (support / "runtime.new").exists()
    (package / "runtime.tar.gz").unlink()  # installed now: the next start must not need the archive
    start()


# --- Uninstall: everything the course tools keep on the computer, after a confirmation --------------------------------------------

import socket  # noqa: E402

WINDOWS_ONLY = pytest.mark.skipif(sys.platform != "win32", reason="Uninstall.bat is for Windows")
UNINSTALL_KINDS = [pytest.param("bat", marks=WINDOWS_ONLY), pytest.param("command", marks=needs_bash)]


def run_uninstall(kind, tmp_path, answer, installed=True, running_port=None):
    """The real Uninstall.bat / Uninstall.command against a made-up profile.

    Returns (result, [the three folders the tools own], [things of other people that must stay])."""
    local, home, temp = tmp_path / "local", tmp_path / "home", tmp_path / "temp"
    for folder in (local, home, temp):
        folder.mkdir(parents=True)
    if kind == "bat":
        tools, work, copies = local / "hs-marimo26", home / ".hs-marimo26", temp / "bpm-provenance"
    else:
        tools, work, copies = home / "Library" / "Application Support" / "hs-marimo26", home / ".hs-marimo26", temp / "bpm-provenance"
    if installed:
        (tools / "runtime" / "python").mkdir(parents=True)
        (tools / "runtime" / "python" / "python3").write_text("x")
        (work / "provenance").mkdir(parents=True)
        (work / "provenance" / "history.db").write_bytes(b"x" * 2048)
        (work / "consent.json").write_text("{}")
        (copies / "abc").mkdir(parents=True)
        (copies / "abc" / "p.db").write_bytes(b"y" * 1024)
    if running_port is not None:
        work.mkdir(parents=True, exist_ok=True)
        (work / "running.port").write_text(str(running_port))
    # what belongs to somebody else, and must stay
    (local / "other-app").mkdir()
    (home / ".marimo").mkdir()
    (temp / "keep.txt").write_text("keep")
    bystanders = [local / "other-app", home / ".marimo", temp / "keep.txt"]
    env = {**os.environ, "LOCALAPPDATA": str(local), "USERPROFILE": str(home), "HOME": home.as_posix(), "TEMP": str(temp), "TMP": str(temp)}
    env["TMPDIR"] = temp.as_posix()
    if kind == "bat":
        command = ["cmd.exe", "/c", str(ROOT / "launcher" / "Uninstall.bat")]
    else:
        command = [BASH, (ROOT / "launcher" / "Uninstall.command").as_posix()]
    # the bytes a keyboard sends on that system: Windows ends a line with CR LF, a Mac with LF alone (bash would read "YES\r" otherwise)
    typed = answer.replace("\n", "\r\n") if kind == "bat" else answer
    raw = subprocess.run(command, input=typed.encode(), env=env, capture_output=True, timeout=240)
    done = subprocess.CompletedProcess(
        raw.args, raw.returncode, raw.stdout.decode("utf8", "replace").replace("\r\n", "\n"), raw.stderr.decode("utf8", "replace")
    )
    return done, [tools, work, copies], bystanders


@pytest.mark.parametrize("kind", UNINSTALL_KINDS)
def test_uninstall_shows_what_goes_and_what_it_means_before_asking(kind, tmp_path):
    done, _, _ = run_uninstall(kind, tmp_path, "no\n")
    text = done.stdout
    for expected in ("provenance", "ONLY on this computer", "course server", "same key", "Type YES"):
        assert expected in text, expected
    assert text.index("ONLY on this computer") < text.index("Type YES")  # the impact is shown first, the question comes last


@pytest.mark.parametrize("kind", UNINSTALL_KINDS)
@pytest.mark.parametrize("answer", ["no\n", "\n", "y\n", "YES please\n", ""])
def test_uninstall_removes_nothing_unless_the_answer_is_yes(kind, answer, tmp_path):
    done, owned, bystanders = run_uninstall(kind, tmp_path, answer)
    assert done.returncode == 0
    assert "Cancelled" in done.stdout
    assert all(folder.exists() for folder in owned + bystanders)


@pytest.mark.parametrize("kind", UNINSTALL_KINDS)
@pytest.mark.parametrize("answer", ["YES\n", "yes\n"])
def test_uninstall_removes_the_three_folders_of_the_tools_and_nothing_else(kind, answer, tmp_path):
    done, owned, bystanders = run_uninstall(kind, tmp_path, answer)
    assert done.returncode == 0, done.stdout + done.stderr
    assert not any(folder.exists() for folder in owned)
    assert all(thing.exists() for thing in bystanders)  # other people's folders, such as the user's own marimo settings, stay
    assert "removed" in done.stdout


@pytest.mark.parametrize("kind", UNINSTALL_KINDS)
def test_uninstall_refuses_while_the_notebooks_are_running(kind, tmp_path):
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        done, owned, _ = run_uninstall(kind, tmp_path, "YES\n", running_port=server.getsockname()[1])
    assert done.returncode != 0
    assert "running" in done.stdout
    assert all(folder.exists() for folder in owned)


@pytest.mark.parametrize("kind", UNINSTALL_KINDS)
def test_uninstall_with_a_stale_port_file_is_not_fooled(kind, tmp_path):
    with socket.socket() as spare:
        spare.bind(("127.0.0.1", 0))
        port = spare.getsockname()[1]  # nothing listens on it once the socket is closed
    done, owned, _ = run_uninstall(kind, tmp_path, "YES\n", running_port=port)
    assert done.returncode == 0, done.stdout + done.stderr
    assert not any(folder.exists() for folder in owned)


@pytest.mark.parametrize("kind", UNINSTALL_KINDS)
def test_uninstall_with_nothing_installed_says_so(kind, tmp_path):
    done, _, bystanders = run_uninstall(kind, tmp_path, "YES\n", installed=False)
    assert done.returncode == 0
    assert "Nothing to remove" in done.stdout
    assert all(thing.exists() for thing in bystanders)


def test_the_package_ships_the_uninstall_script_of_each_system(tmp_path):
    with zipfile.ZipFile(build_package(tmp_path)) as z:
        assert "Uninstall.bat" in z.namelist() and "Uninstall.command" not in z.namelist()
    with zipfile.ZipFile(build_package(tmp_path / "mac", os_name="macos-arm64")) as z:
        assert "Uninstall.command" in z.namelist() and "Uninstall.bat" not in z.namelist()


def test_the_package_id_names_the_build_when_there_is_one(tmp_path):
    # a version published again must unpack again on a computer that already has it: the id names the build, the version stays plain
    with zipfile.ZipFile(build_package(tmp_path, build_id="abc1234")) as z:
        assert z.read("package-id.txt").decode("utf8").strip() == "1.2.3-abc1234"
    assert json.loads(inner_zip(build_package(tmp_path / "again", build_id="abc1234")).read("version.json")) == {"version": "1.2.3"}


def test_start_here_explains_how_to_remove_everything():
    text = (ROOT / "launcher" / "START-HERE.txt").read_text(encoding="utf8")
    for expected in ("REMOVING EVERYTHING", "Uninstall", "YES", "course server"):
        assert expected in text, expected
