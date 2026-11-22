"""The notebooks' own check of the student's answer about sharing (`ak.course_server`), against what the launcher writes."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "launcher"))
sys.path.insert(0, str(ROOT / "notebooks" / "lib"))
import consent  # noqa: E402
import initial_analysis_kit as ak  # noqa: E402

SERVER = "https://provenance.example"


def answer(home: Path, choice: str) -> None:
    """The launcher records an answer, in the folder the notebooks read it from."""
    consent.save(home / ".hs-marimo26", choice)


def test_a_student_who_said_no_has_no_server_whatever_the_notebook_was_started_with(tmp_path):
    answer(tmp_path, "declined")
    assert ak.sharing_allowed(tmp_path) is False
    assert ak.course_server(SERVER, tmp_path) == ""


def test_a_student_who_said_yes_keeps_the_server(tmp_path):
    answer(tmp_path, "accepted")
    assert ak.sharing_allowed(tmp_path) is True
    assert ak.course_server(SERVER, tmp_path) == SERVER


def test_changing_the_answer_changes_what_the_next_start_of_a_notebook_gets(tmp_path):
    answer(tmp_path, "accepted")
    assert ak.course_server(SERVER, tmp_path) == SERVER
    answer(tmp_path, "declined")
    assert ak.course_server(SERVER, tmp_path) == ""
    answer(tmp_path, "accepted")
    assert ak.course_server(SERVER, tmp_path) == SERVER


def test_without_an_answer_file_nothing_is_held_back(tmp_path):
    # a hosted or a development copy: the student package was never started here, so there is no answer to respect
    assert ak.sharing_allowed(tmp_path) is True
    assert ak.course_server(SERVER, tmp_path) == SERVER


def test_no_server_stays_no_server_also_for_a_student_who_said_yes(tmp_path):
    answer(tmp_path, "accepted")
    assert ak.course_server("", tmp_path) == ""  # the launcher, or the teacher, switched the server off


@pytest.mark.parametrize("text", [
    "not json",
    "",
    "[]",
    "null",
    json.dumps({"choice": "accepted"}),  # no version
    json.dumps({"version": 1}),  # no choice
    json.dumps({"version": 1, "choice": "ACCEPTED"}),
    json.dumps({"version": 1, "choice": "undecided"}),
    json.dumps({"version": 1, "choice": True}),
])
def test_an_answer_that_cannot_be_read_as_a_yes_counts_as_no(tmp_path, text):
    (tmp_path / ".hs-marimo26").mkdir()
    (tmp_path / ".hs-marimo26" / "consent.json").write_text(text, encoding="utf8")
    assert ak.course_server(SERVER, tmp_path) == ""


def test_a_yes_given_for_another_consent_text_counts_as_no(tmp_path):
    (tmp_path / ".hs-marimo26").mkdir()
    record = {"version": ak.CONSENT_VERSION + 1, "choice": "accepted"}
    (tmp_path / ".hs-marimo26" / "consent.json").write_text(json.dumps(record), encoding="utf8")
    assert ak.course_server(SERVER, tmp_path) == ""


def test_the_answer_is_read_from_the_home_folder_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert ak.course_server(SERVER) == SERVER
    answer(tmp_path, "declined")
    assert ak.course_server(SERVER) == ""


def test_the_notebooks_and_the_launcher_agree_on_the_consent_text_they_mean():
    assert ak.CONSENT_VERSION == consent.CONSENT_VERSION


def test_every_notebook_that_saves_to_the_course_server_asks_the_students_answer_first():
    # a notebook that read the address straight from the environment would send a "no" student's work when started by hand
    saving = [file for file in sorted((ROOT / "notebooks").glob("*.py")) if "PMPROV_SYNC_URL" in file.read_text(encoding="utf8")]
    assert [file.name for file in saving] == ["02_initial-analysis.py", "03_map-explorer.py"]
    for file in saving:
        source = file.read_text(encoding="utf8")
        assigned = re.findall(r"^\s*SYNC_URL\s*=\s*(.+)$", source, flags=re.M)
        assert len(assigned) == 1 and assigned[0].startswith("ak.course_server("), file.name
        assert "Sync(" in source and re.search(r"if SYNC_URL:\s*\n(?:.*\n){0,6}?.*Sync\(", source), file.name
