import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notebooks" / "lib"))
import initial_analysis_kit as ak  # noqa: E402


def test_the_dhana_log_the_notebooks_load_is_the_fast_parquet():
    assert ak.DHANA == "data/dhana-loan-application.parquet"


def test_load_event_log_reads_a_parquet(tmp_path):
    path = tmp_path / "log.parquet"
    frame = pd.DataFrame({"case_concept_name": ["A1", "A1"], "concept_name": ["x", "y"]})
    frame.to_parquet(path)
    assert ak.load_event_log(path).equals(frame)


def test_the_log_is_not_in_the_repository_only_its_hash_is():
    import subprocess

    root = Path(__file__).resolve().parents[1]
    tracked = subprocess.run(["git", "ls-files", "notebooks/data"], cwd=root, capture_output=True, text=True).stdout.split()
    if not tracked:
        import pytest

        pytest.skip("not a git checkout")
    assert "notebooks/" + ak.DHANA + ".sha256" in tracked
    assert not [name for name in tracked if "dhana" in name and not name.endswith(".sha256")]


def test_a_copy_of_the_log_on_this_computer_is_the_one_the_package_names():
    import hashlib

    import pytest

    path = Path(__file__).resolve().parents[1] / "notebooks" / ak.DHANA
    if not path.is_file():
        pytest.skip("the log is not public: it is only on a computer that fetched it")
    named = Path(str(path) + ".sha256").read_text(encoding="utf8").split()[0]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == named


def test_the_notebooks_can_tell_that_the_log_is_missing(tmp_path):
    assert ak.log_is_missing(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / ak.DHANA).write_bytes(b"x")
    assert not ak.log_is_missing(tmp_path)
    assert "course code" in ak.MISSING_LOG and "Start" in ak.MISSING_LOG
