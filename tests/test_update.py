import io
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "launcher"))
import update  # noqa: E402


def make_zip(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buf.getvalue()


def setup_root(tmp_path, version=None):
    nb = tmp_path / "notebooks"
    (nb / "data").mkdir(parents=True)
    (nb / "provenance").mkdir()
    (nb / "lecture.py").write_text("old")
    (nb / "data" / "big.xes").write_text("DATA")
    (nb / "provenance" / "work.db").write_text("WORK")
    if version is not None:
        (tmp_path / "version.json").write_text(json.dumps(version))
    return tmp_path


def release(n=2, min_runtime=1):
    return {"notebooks": n, "zip_url": "http://x/nb.zip", "min_runtime": min_runtime}


def downloader(payload: bytes):
    def download(url, dest):
        Path(dest).write_bytes(payload)
    return download


def test_newer_release_replaces_notebooks_keeps_data_and_work(tmp_path):
    root = setup_root(tmp_path, {"runtime": 1, "notebooks": 1})
    payload = make_zip({"lecture.py": "new", "lib/a.py": "A"})
    assert update.apply_release(root, release(), downloader(payload)) == "updated"
    assert (root / "notebooks" / "lecture.py").read_text() == "new"
    assert (root / "notebooks" / "lib" / "a.py").read_text() == "A"
    assert (root / "notebooks" / "data" / "big.xes").read_text() == "DATA"
    assert (root / "notebooks" / "provenance" / "work.db").read_text() == "WORK"
    assert update.read_version(root)["notebooks"] == 2


def test_same_version_is_current(tmp_path):
    root = setup_root(tmp_path, {"runtime": 1, "notebooks": 2})
    assert update.apply_release(root, release(2), downloader(b"")) == "current"


def test_download_error_returns_failed_and_leaves_files(tmp_path):
    root = setup_root(tmp_path, {"runtime": 1, "notebooks": 1})

    def boom(url, dest):
        raise OSError("offline")

    assert update.apply_release(root, release(), boom) == "failed"
    assert (root / "notebooks" / "lecture.py").read_text() == "old"


def test_corrupt_zip_leaves_notebooks_untouched(tmp_path):
    root = setup_root(tmp_path, {"runtime": 1, "notebooks": 1})
    assert update.apply_release(root, release(), downloader(b"not a zip")) == "failed"
    assert (root / "notebooks" / "lecture.py").read_text() == "old"
    assert update.read_version(root)["notebooks"] == 1


def test_min_runtime_higher_than_installed_is_not_applied(tmp_path, capsys):
    root = setup_root(tmp_path, {"runtime": 1, "notebooks": 1})
    result = update.apply_release(root, release(min_runtime=2), downloader(make_zip({"lecture.py": "new"})))
    assert result == "needs-runtime"
    assert (root / "notebooks" / "lecture.py").read_text() == "old"
    assert "download" in capsys.readouterr().out.lower()


def test_no_version_file_treated_as_zero(tmp_path):
    assert update.read_version(tmp_path) == {"runtime": 0, "notebooks": 0}


def test_latest_release_picks_highest_notebooks_tag_and_survives_errors():
    data = [
        {"tag_name": "runtime-1", "assets": []},
        {"tag_name": "notebooks-2", "body": '{"min_runtime": 1}', "assets": [{"name": "notebooks.zip", "browser_download_url": "u2"}]},
        {"tag_name": "notebooks-10", "body": '{"min_runtime": 1}', "assets": [{"name": "notebooks.zip", "browser_download_url": "u10"}]},
    ]
    assert update.latest_release("o/r", fetch=lambda url: data) == {"notebooks": 10, "zip_url": "u10", "min_runtime": 1}

    def boom(url):
        raise OSError("offline")

    assert update.latest_release("o/r", fetch=boom) is None
