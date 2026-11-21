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


def setup_root(tmp_path, version="1.0.0"):
    nb = tmp_path / "notebooks"
    (nb / "data").mkdir(parents=True)
    (nb / "provenance").mkdir()
    (nb / "lecture.py").write_text("old")
    (nb / "data" / "big.xes").write_text("DATA")
    (nb / "provenance" / "work.db").write_text("WORK")
    if version is not None:
        (tmp_path / "version.json").write_text(json.dumps({"version": version}))
    return tmp_path


def release(version=(1, 1, 0)):
    return {"version": version, "zip_url": "http://x/nb.zip"}


def downloader(payload: bytes):
    def download(url, dest):
        Path(dest).write_bytes(payload)
    return download


def test_newer_minor_release_replaces_notebooks_keeps_data_and_work(tmp_path):
    root = setup_root(tmp_path, "1.0.0")
    payload = make_zip({"lecture.py": "new", "lib/a.py": "A"})
    assert update.apply_release(root, release((1, 1, 0)), downloader(payload)) == "updated"
    assert (root / "notebooks" / "lecture.py").read_text() == "new"
    assert (root / "notebooks" / "lib" / "a.py").read_text() == "A"
    assert (root / "notebooks" / "data" / "big.xes").read_text() == "DATA"
    assert (root / "notebooks" / "provenance" / "work.db").read_text() == "WORK"
    assert update.read_version(root) == (1, 1, 0)


def test_patch_release_is_applied_too(tmp_path):
    root = setup_root(tmp_path, "1.2.0")
    assert update.apply_release(root, release((1, 2, 1)), downloader(make_zip({"lecture.py": "p"}))) == "updated"


def test_same_or_older_version_is_current(tmp_path):
    root = setup_root(tmp_path, "1.2.0")
    assert update.apply_release(root, release((1, 2, 0)), downloader(b"")) == "current"
    assert update.apply_release(root, release((1, 1, 9)), downloader(b"")) == "current"


def test_download_error_returns_failed_and_leaves_files(tmp_path):
    root = setup_root(tmp_path, "1.0.0")

    def boom(url, dest):
        raise OSError("offline")

    assert update.apply_release(root, release(), boom) == "failed"
    assert (root / "notebooks" / "lecture.py").read_text() == "old"


def test_corrupt_zip_leaves_notebooks_untouched(tmp_path):
    root = setup_root(tmp_path, "1.0.0")
    assert update.apply_release(root, release(), downloader(b"not a zip")) == "failed"
    assert (root / "notebooks" / "lecture.py").read_text() == "old"
    assert update.read_version(root) == (1, 0, 0)


def test_newer_major_is_not_applied_and_tells_the_student_to_download(tmp_path, capsys):
    root = setup_root(tmp_path, "1.4.0")
    result = update.apply_release(root, release((2, 0, 0)), downloader(make_zip({"lecture.py": "new"})))
    assert result == "needs-package"
    assert (root / "notebooks" / "lecture.py").read_text() == "old"
    assert "download" in capsys.readouterr().out.lower()


def test_no_version_file_or_garbage_is_version_zero(tmp_path):
    assert update.read_version(tmp_path) == (0, 0, 0)
    (tmp_path / "version.json").write_text("{not json")
    assert update.read_version(tmp_path) == (0, 0, 0)


def test_parse_version_accepts_a_v_prefix_and_rejects_other_tags():
    assert update.parse_version("v1.2.3") == (1, 2, 3)
    assert update.parse_version("1.2.3") == (1, 2, 3)
    for bad in ("runtime-1", "v1.2", "latest", ""):
        assert update.parse_version(bad) is None


def test_latest_release_reads_the_public_latest_page_and_never_asks_the_api():
    asked = []

    def where(url):
        asked.append(url)
        return "https://github.com/o/r/releases/tag/v1.3.0"

    assert update.latest_release("o/r", resolve=where) == {
        "version": (1, 3, 0), "zip_url": "https://github.com/o/r/releases/download/v1.3.0/notebooks.zip"}
    assert asked == ["https://github.com/o/r/releases/latest"]  # a page, not the API: no limit on requests for a classroom

    assert update.latest_release("o/r", resolve=lambda url: "https://github.com/o/r/releases/tag/datasets") is None
    assert update.latest_release("o/r", resolve=lambda url: "https://github.com/o/r/releases") is None  # nothing published yet
    assert update.latest_release("o/r", resolve=lambda url: None) is None

    def boom(url):
        raise OSError("offline")

    assert update.latest_release("o/r", resolve=boom) is None


def manifest(files, requirements=None):
    return json.dumps({"files": files, **({"requirements": requirements} if requirements else {})})


def test_a_notebook_the_new_release_no_longer_has_is_removed_and_the_students_own_files_stay(tmp_path):
    root = setup_root(tmp_path, "1.0.0")
    nb = root / "notebooks"
    (nb / "old_helper.py").write_text("x")
    (nb / "mine.py").write_text("the student's own")
    (root / "manifest.json").write_text(manifest(["lecture.py", "old_helper.py"]))
    payload = make_zip({"00_lecture.py": "new", "manifest.json": manifest(["00_lecture.py"])})

    assert update.apply_release(root, release((1, 1, 0)), downloader(payload)) == "updated"

    assert sorted(p.name for p in nb.iterdir()) == ["00_lecture.py", "data", "mine.py", "provenance"]
    assert json.loads((root / "manifest.json").read_text())["files"] == ["00_lecture.py"]  # what the next update compares with
    assert (nb / "data" / "big.xes").read_text() == "DATA" and (nb / "provenance" / "work.db").read_text() == "WORK"


def test_without_a_list_of_what_was_installed_nothing_is_removed(tmp_path):
    root = setup_root(tmp_path, "1.0.0")
    payload = make_zip({"00_lecture.py": "new", "manifest.json": manifest(["00_lecture.py"])})
    assert update.apply_release(root, release((1, 1, 0)), downloader(payload)) == "updated"
    assert (root / "notebooks" / "lecture.py").read_text() == "old"


def test_a_list_can_never_remove_the_students_work_the_datasets_or_anything_outside_the_notebooks(tmp_path):
    root = setup_root(tmp_path, "1.0.0")
    (root / "manifest.json").write_text(manifest(["../version.json", "data/big.xes", "provenance/work.db", "/etc/x", ""]))
    payload = make_zip({"lecture.py": "new", "manifest.json": manifest(["lecture.py"])})
    assert update.apply_release(root, release((1, 1, 0)), downloader(payload)) == "updated"
    assert (root / "notebooks" / "data" / "big.xes").exists() and (root / "notebooks" / "provenance" / "work.db").exists()
    assert update.read_version(root) == (1, 1, 0)


def test_notebooks_made_for_other_libraries_are_not_applied_whatever_their_version_says(tmp_path):
    root = setup_root(tmp_path, "1.0.0")
    (root / "manifest.json").write_text(manifest(["lecture.py"], requirements="aaa"))
    payload = make_zip({"lecture.py": "needs a new library", "manifest.json": manifest(["lecture.py"], requirements="bbb")})

    assert update.apply_release(root, release((1, 1, 0)), downloader(payload)) == "needs-package"

    assert (root / "notebooks" / "lecture.py").read_text() == "old" and update.read_version(root) == (1, 0, 0)
    same = make_zip({"lecture.py": "new", "manifest.json": manifest(["lecture.py"], requirements="aaa")})
    assert update.apply_release(root, release((1, 1, 0)), downloader(same)) == "updated"
