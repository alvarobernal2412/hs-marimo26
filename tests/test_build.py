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
            "Start.bat", "Change-my-answer.bat", "README-students.md", "package-id.txt", "runtime.zip",
            "launcher/start.py", "launcher/update.py", "launcher/consent.py",
        }


def test_package_id_is_the_version(tmp_path):
    with zipfile.ZipFile(build_package(tmp_path)) as z:
        assert z.read("package-id.txt").decode("utf8").strip() == "1.2.3"


def test_runtime_zip_holds_python_notebooks_and_version(tmp_path):
    names = set(inner_zip(build_package(tmp_path)).namelist())
    for expected in ("python/python.exe", "notebooks/lecture.py", "notebooks/data/dhana-loan-application-molab.xes", "version.json"):
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
        assert t.getmember("notebooks/lecture.py").mode & 0o777 == 0o644
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
