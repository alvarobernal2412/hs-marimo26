"""The copy of marimo-pmprov that comes with the notebooks (`notebooks/vendor`), which a start brings up to date with them."""
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(ROOT / "launcher"))
import make_notebooks_zip  # noqa: E402
import update  # noqa: E402
import vendor_library  # noqa: E402

VENDOR = ROOT / "notebooks" / "vendor"


def record():
    return json.loads((VENDOR / vendor_library.RECORD).read_text(encoding="utf8"))


def test_the_copy_is_the_one_the_record_names_and_was_not_edited_by_hand():
    assert record()["sha256"] == vendor_library.tree_hash(VENDOR / "provenance_widget"), (
        "notebooks/vendor/provenance_widget differs from what build/vendor_library.py put there: change marimo-pmprov and vendor it again"
    )
    assert record()["package"] == "marimo-pmprov" and record()["version"]


def test_the_copy_is_complete_and_has_no_caches():
    files = {f.relative_to(VENDOR).as_posix() for f in VENDOR.rglob("*") if f.is_file() and "__pycache__" not in f.parts}
    for needed in ("__init__.py", "widget.py", "pmprov_adapter.py", "sync.py", "static/widget.js", "static/widget.css"):
        assert f"provenance_widget/{needed}" in files
    assert not [f for f in files if f.endswith(".pyc")]


def test_the_copy_is_not_older_than_what_the_package_installs():
    """The notebooks are written for the copy: the installed library is only what is used when there is none."""
    required = next(line for line in (ROOT / "build" / "requirements.txt").read_text(encoding="utf8").splitlines() if line.startswith("marimo-pmprov"))
    floor = tuple(int(n) for n in required.split(">=")[1].split("."))
    assert tuple(int(n) for n in record()["version"].split(".")) >= floor


def test_a_release_of_the_notebooks_ships_the_copy(tmp_path):
    names = {name for _, name in make_notebooks_zip.shipped_files(ROOT / "notebooks")}
    assert {"vendor/VENDORED.json", "vendor/provenance_widget/widget.py", "vendor/provenance_widget/static/widget.js"} <= names
    assert any(name.startswith("vendor/provenance_widget/") and name.endswith(".ttf") for name in names)  # the report's fonts


def test_a_start_replaces_the_copy_a_student_has_by_the_one_of_the_release(tmp_path):
    """What `Start` does with a newer release of the same MAJOR: the whole `notebooks/vendor` is the release's afterwards."""
    archive = tmp_path / "notebooks.zip"
    make_notebooks_zip.make_zip(ROOT / "notebooks", archive, ROOT / "build" / "requirements.txt", "test")
    installed = tmp_path / "runtime"
    old = installed / "notebooks" / "vendor" / "provenance_widget"
    old.mkdir(parents=True)
    (old / "widget.py").write_text("OLD = True\n", encoding="utf8")
    (old / "gone_in_the_new_version.py").write_text("", encoding="utf8")
    (installed / "version.json").write_text(json.dumps({"version": "1.0.0"}), encoding="utf8")
    before = make_notebooks_zip.manifest(ROOT / "notebooks", ROOT / "build" / "requirements.txt", "before")
    before["files"] += ["vendor/provenance_widget/gone_in_the_new_version.py"]
    (installed / "manifest.json").write_text(json.dumps(before), encoding="utf8")

    release = {"version": (1, 1, 0), "zip_url": "the release"}
    assert update.apply_release(installed, release, download=lambda url, dest: Path(dest).write_bytes(archive.read_bytes())) == "updated"

    assert vendor_library.tree_hash(installed / "notebooks" / "vendor" / "provenance_widget") == record()["sha256"]
    assert not (old / "gone_in_the_new_version.py").exists()
    assert json.loads((installed / "version.json").read_text(encoding="utf8")) == {"version": "1.1.0"}


def test_python_imports_the_copy_before_an_installed_one(tmp_path):
    """As the notebooks do: `notebooks/vendor` first on the path. Run in a Python of its own, so nothing is imported yet."""
    installed = tmp_path / "site-packages" / "provenance_widget"
    installed.mkdir(parents=True)
    (installed / "__init__.py").write_text("", encoding="utf8")
    code = (
        "import sys; sys.path.insert(0, sys.argv[2]); sys.path.insert(0, sys.argv[1]);"
        "import provenance_widget; print(provenance_widget.__file__)"
    )
    out = subprocess.run([sys.executable, "-c", code, str(VENDOR), str(installed.parent)], capture_output=True, text=True, check=True)
    assert Path(out.stdout.strip()).parent == VENDOR / "provenance_widget"


def test_vendoring_copies_a_built_module_and_records_it(tmp_path):
    source = tmp_path / "checkout" / "provenance_widget"
    (source / "static").mkdir(parents=True)
    (source / "__pycache__").mkdir()
    (source / "__init__.py").write_text("", encoding="utf8")
    (source / "static" / "widget.js").write_text("export default {};\n", encoding="utf8")
    (source / "static" / ".gitkeep").write_text("", encoding="utf8")
    (source / "__pycache__" / "x.pyc").write_bytes(b"cache")
    target = tmp_path / "vendor"
    (target / "provenance_widget").mkdir(parents=True)
    (target / "provenance_widget" / "left_over.py").write_text("", encoding="utf8")

    made = vendor_library.vendor(source, "9.9.9", "a test", target)

    copied = sorted(f.relative_to(target).as_posix() for f in target.rglob("*") if f.is_file())
    assert copied == ["VENDORED.json", "provenance_widget/__init__.py", "provenance_widget/static/widget.js"]
    assert made["version"] == "9.9.9" and made["sha256"] == vendor_library.tree_hash(target / "provenance_widget")
    # the hash is of the contents, whatever the line endings of a checkout
    (target / "provenance_widget" / "static" / "widget.js").write_bytes(b"export default {};\r\n")
    assert vendor_library.tree_hash(target / "provenance_widget") == made["sha256"]
    with pytest.raises(SystemExit):
        vendor_library.vendor(tmp_path, "1", "not a module", target)


def test_a_wheel_is_vendored_under_its_version(tmp_path, monkeypatch):
    wheel = tmp_path / "marimo_pmprov-9.9.9-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as z:
        z.writestr("provenance_widget/__init__.py", "")
        z.writestr("provenance_widget/static/widget.js", "export default {};\n")
        z.writestr("marimo_pmprov-9.9.9.dist-info/METADATA", "Name: marimo-pmprov\n")
    monkeypatch.setattr(vendor_library, "VENDOR", tmp_path / "vendor")
    monkeypatch.setattr(vendor_library.vendor, "__defaults__", (tmp_path / "vendor",))
    assert vendor_library.main(["--wheel", str(wheel)]) == 0
    made = json.loads((tmp_path / "vendor" / "VENDORED.json").read_text(encoding="utf8"))
    assert made["version"] == "9.9.9" and made["from"] == f"wheel {wheel.name}"
    assert (tmp_path / "vendor" / "provenance_widget" / "static" / "widget.js").is_file()
