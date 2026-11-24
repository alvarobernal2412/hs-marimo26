import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notebooks" / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notebooks"))
import initial_analysis_kit as ak  # noqa: E402
import bpm_kit as kit  # noqa: E402


def _log(rows=300):
    return pd.DataFrame(
        {
            ak.CASE_ID: [f"c{i % 30}" for i in range(rows)],
            ak.ACTIVITY: [("a", "b", "c")[i % 3] for i in range(rows)],
            "lifecycle_transition": [("start", "complete")[i % 2] for i in range(rows)],
            "EventID": [f"e{i}" for i in range(rows)],
            "constant": ["x"] * rows,
            "amount": [float(i) for i in range(rows)],
            ak.TIMESTAMP: pd.date_range("2024-01-01", periods=rows, freq="h"),
        }
    ).rename(columns={ak.ACTIVITY: "concept_name"})


def test_activity_options_start_with_the_activity_and_skip_ids():
    assert ak.activity_column_options(_log()) == ["concept_name", "lifecycle_transition"]


def test_to_lcm_log_takes_another_activity_column():
    log = _log(10)
    log.loc[3, "lifecycle_transition"] = None
    out = ak.to_lcm_log(log, ak.CASE_ID, "lifecycle_transition")
    expected = log["lifecycle_transition"].dropna()
    assert list(out["concept:name"]) == list(expected)
    assert len(out) == 9


def test_to_lcm_log_with_one_column_for_both():
    out = ak.to_lcm_log(_log(10), "lifecycle_transition", "lifecycle_transition")
    assert list(out.columns) == ["case:concept:name", "concept:name", "time:timestamp"]
    assert (out["case:concept:name"] == out["concept:name"]).all()


def test_the_map_service_is_not_reused_for_another_log(monkeypatch):
    class FakeLcm:
        @staticmethod
        def get_service(events):
            return object()

    monkeypatch.setattr(kit, "lcm", FakeLcm)
    a, b = ak.to_lcm_log(_log(10)), ak.to_lcm_log(_log(10))  # two frames of the same length
    first = kit._service(a, "application")[0]
    assert kit._service(a, "application")[0] is first
    assert kit._service(b, "application")[0] is not first
