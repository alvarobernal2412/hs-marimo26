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
