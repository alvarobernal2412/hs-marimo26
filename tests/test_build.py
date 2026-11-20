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


def test_layout_has_expected_paths_and_zip(tmp_path):
    python_dir = tmp_path / "py"
    (python_dir).mkdir()
    (python_dir / "python.exe").write_text("")
    data = tmp_path / "data"
    data.mkdir()
    (data / "dhana-loan-application-molab.xes").write_text("X")
    out = tmp_path / "out"
    zip_path = br.assemble(ROOT, python_dir, data, out, os_name="windows-x64", version="1.2.3")
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
    assert zip_path.name == "hs-marimo26-v1.2.3-windows-x64.zip"
    for expected in ("Start.bat", "python/python.exe", "launcher/start.py", "launcher/update.py", "launcher/consent.py", "version.json",
                     "notebooks/lecture.py", "notebooks/data/dhana-loan-application-molab.xes"):
        assert expected in names, expected
    assert "Start.command" not in names


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
