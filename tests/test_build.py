import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import build_runtime as br  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_render_version_json():
    assert json.loads(br.render_version_json(3, 7)) == {"runtime": 3, "notebooks": 7}


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
    zip_path = br.assemble(ROOT, python_dir, data, out, os_name="windows-x64", runtime=1, notebooks=1)
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
    assert zip_path.name == "hs-marimo26-windows-x64-runtime1.zip"
    for expected in ("Start.bat", "python/python.exe", "launcher/start.py", "launcher/update.py", "version.json",
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
