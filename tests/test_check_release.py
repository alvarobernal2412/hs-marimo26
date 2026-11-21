"""build/check_release.py: a release that changes the libraries has to be a new MAJOR version, because only a new package (not the
launcher's own update of the notebooks) can bring libraries to a student."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import check_release as cr  # noqa: E402


def test_changed_libraries_under_the_same_major_are_refused_with_a_reason():
    problem = cr.problem(previous=((1, 2, 0), "aaa"), version=(1, 3, 0), requirements="bbb")
    assert problem and "2.0.0" in problem and "requirements" in problem


def test_the_same_libraries_or_a_new_major_or_no_earlier_release_are_fine():
    assert cr.problem(previous=((1, 2, 0), "aaa"), version=(1, 3, 0), requirements="aaa") is None
    assert cr.problem(previous=((1, 2, 0), "aaa"), version=(2, 0, 0), requirements="bbb") is None
    assert cr.problem(previous=None, version=(1, 0, 0), requirements="bbb") is None
    assert cr.problem(previous=((1, 2, 0), None), version=(1, 3, 0), requirements="bbb") is None  # a release from before the list
    assert cr.problem(previous=((1, 2, 0), "aaa"), version=(1, 2, 0), requirements="bbb") is None  # the same version, built again


def test_the_published_release_is_read_from_its_notebooks_zip(tmp_path):
    import json
    import zipfile

    def download(url, dest):
        assert url == "https://x/notebooks.zip"
        with zipfile.ZipFile(dest, "w") as z:
            z.writestr("manifest.json", json.dumps({"files": [], "requirements": "aaa"}))

    assert cr.published(find=lambda: {"version": (1, 2, 0), "zip_url": "https://x/notebooks.zip"}, download=download) == ((1, 2, 0), "aaa")
    assert cr.published(find=lambda: None, download=download) is None


def test_the_release_workflow_runs_the_check_before_it_drafts_anything():
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "release.yml").read_text(encoding="utf8")
    assert "build/check_release.py" in workflow
    assert workflow.index("build/check_release.py") < workflow.index("Build the zip")
