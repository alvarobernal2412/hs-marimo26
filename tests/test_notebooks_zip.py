import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import make_notebooks_zip as mz  # noqa: E402


def test_zip_excludes_xes_and_caches_but_includes_lib(tmp_path):
    nb = tmp_path / "notebooks"
    (nb / "lib" / "__pycache__").mkdir(parents=True)
    (nb / "data").mkdir()
    (nb / "provenance").mkdir()
    (nb / "lecture.py").write_text("x")
    (nb / "lib" / "a.py").write_text("x")
    (nb / "lib" / "__pycache__" / "a.pyc").write_text("x")
    (nb / "data" / "big.xes").write_text("x")
    (nb / "data" / "small.csv").write_text("x")
    (nb / "provenance" / "work.db").write_text("x")
    out = tmp_path / "notebooks.zip"
    mz.make_zip(nb, out)
    names = set(zipfile.ZipFile(out).namelist())
    assert names == {"lecture.py", "lib/a.py", "data/small.csv"}
