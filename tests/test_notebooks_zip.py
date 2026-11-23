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
    (nb / "data" / "private.parquet").write_text("x")  # a developer has it; its hash next to it says it is not public
    (nb / "data" / "private.parquet.sha256").write_text("abc")
    (nb / "provenance" / "work.db").write_text("x")
    out = tmp_path / "notebooks.zip"
    mz.make_zip(nb, out)
    names = set(zipfile.ZipFile(out).namelist())
    assert names == {"lecture.py", "lib/a.py", "data/small.csv", "data/private.parquet.sha256", "manifest.json"}


def test_zip_says_which_files_it_ships_and_which_libraries_they_were_made_for(tmp_path):
    import json

    nb = tmp_path / "notebooks"
    (nb / "lib").mkdir(parents=True)
    (nb / "lecture.py").write_text("x")
    (nb / "lib" / "a.py").write_text("x")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("marimo==0.25.2\npandas>=3.1.0\n")
    out = tmp_path / "notebooks.zip"
    mz.make_zip(nb, out, requirements)
    found = json.loads(zipfile.ZipFile(out).read("manifest.json"))
    assert found == {"files": ["lecture.py", "lib/a.py"], "requirements": mz.requirements_hash(requirements)}


def test_zip_names_its_build_and_leaves_the_same_manifest_next_to_it_for_the_release(tmp_path):
    import json

    nb = tmp_path / "notebooks"
    nb.mkdir()
    (nb / "lecture.py").write_text("x")
    (tmp_path / "out").mkdir()
    out = tmp_path / "out" / "notebooks.zip"
    mz.make_zip(nb, out, build_id="abc1234")
    found = json.loads(zipfile.ZipFile(out).read("manifest.json"))
    assert found == {"files": ["lecture.py"], "build": "abc1234"}
    assert json.loads((tmp_path / "out" / "manifest.json").read_text(encoding="utf8")) == found  # what a launcher asks first


def test_the_libraries_hash_changes_with_a_library_and_not_with_comments_or_order(tmp_path):
    a, b, c = tmp_path / "a.txt", tmp_path / "b.txt", tmp_path / "c.txt"
    a.write_text("marimo==0.25.2\npandas>=3.1.0\n")
    b.write_text("# the notebooks' libraries\n\npandas>=3.1.0  \nmarimo==0.25.2\n")
    c.write_text("marimo==0.25.2\npandas>=3.1.0\nscipy\n")
    assert mz.requirements_hash(a) == mz.requirements_hash(b) != mz.requirements_hash(c)
