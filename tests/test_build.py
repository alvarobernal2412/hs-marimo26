import json
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


def build_package(tmp_path, os_name="windows-x64", version="1.2.3"):
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
    return br.assemble(ROOT, python_dir, data, tmp_path / "out", os_name=os_name, version=version)


def inner_zip(outer_path: Path, name: str = "runtime.zip") -> zipfile.ZipFile:
    import io

    with zipfile.ZipFile(outer_path) as outer:
        return zipfile.ZipFile(io.BytesIO(outer.read(name)))


def test_outer_zip_has_only_the_expected_entries(tmp_path):
    zip_path = build_package(tmp_path)
    assert zip_path.name == "hs-marimo26-v1.2.3-windows-x64.zip"
    with zipfile.ZipFile(zip_path) as z:
        assert set(z.namelist()) == {
            "Start.bat", "Change-my-answer.bat", "START-HERE.txt", "package-id.txt", "runtime.zip",
            "launcher/start.py", "launcher/update.py", "launcher/consent.py",
        }


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


def test_student_readme_has_no_terminal_instructions():
    text = (ROOT / "launcher" / "START-HERE.txt").read_text(encoding="utf8")
    assert "Change-my-answer" in text
    assert "--consent" not in text and "terminal" not in text.lower()  # students never open a terminal
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


def test_student_readme_explains_current_mac_and_managed_laptop_blocks():
    text = (ROOT / "launcher" / "START-HERE.txt").read_text(encoding="utf8")
    assert "Privacy & Security" in text and "Open Anyway" in text  # macOS 15 removed the right-click override
    assert "IT department" in text  # a university-managed laptop may need its IT team to allow the folder


def test_start_command_unpacks_once_with_tar_and_passes_flags():
    text = (ROOT / "launcher" / "Start.command").read_text(encoding="utf8")
    for expected in ("Library/Application Support/hs-marimo26/runtime", "package-id.txt", "ready-", "/usr/bin/tar -xzf", '"$@"'):
        assert expected in text, expected
    assert '"$RT.new"' in text and "python/bin/python3" in text  # unpacked beside the runtime, swapped in only when complete
    assert text.index("rm -rf \"$NEW\"") < text.index("/usr/bin/tar -xzf") < text.index("touch ") < text.index("mv ")
