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


def _three_cases():
    days = [0, 1, 2, 3, 4, 5]
    return pd.DataFrame(
        {
            ak.CASE_ID: ["a", "a", "b", "b", "c", "c"],
            ak.ACTIVITY: ["x", "y", "x", "y", "x", "y"],
            ak.TIMESTAMP: [pd.Timestamp("2024-01-01") + pd.Timedelta(days=d) for d in days],
        }
    )


def test_a_time_frame_keeps_only_the_cases_completely_inside_it():
    out = ak.to_lcm_log(_three_cases(), ak.CASE_ID, ak.ACTIVITY, [0, 4])
    assert sorted(out["case:concept:name"].unique()) == ["a", "b"]
    assert len(ak.to_lcm_log(_three_cases())) == 6
    assert len(ak.to_lcm_log(_three_cases(), window=None)) == 6


def test_a_time_frame_agrees_with_the_initial_analysis_filter():
    log = _three_cases()
    frame = ak.time_frame(log, ak.CASE_ID, ak.TIMESTAMP)
    start = frame["start"] + pd.Timedelta(0, frame["unit"])
    end = frame["start"] + pd.Timedelta(1, frame["unit"])
    kept = ak.tcu.filter_cases_within_window(log, ak.CASE_ID, ak.TIMESTAMP, start, end)
    assert len(ak.to_lcm_log(log, ak.CASE_ID, ak.ACTIVITY, [0, 1])) == len(kept)


def test_a_time_frame_without_a_complete_case_gives_an_empty_log():
    out = ak.to_lcm_log(_three_cases(), ak.CASE_ID, ak.ACTIVITY, [0, 0])
    assert out.empty
    assert list(out.columns) == ["case:concept:name", "concept:name", "time:timestamp"]


def test_cases_in_time_frame_counts_cases_and_events():
    assert ak.cases_in_time_frame(_three_cases(), [0, 4]) == (2, 4)
    assert ak.cases_in_time_frame(_three_cases(), [0, 5]) == (3, 6)


import pytest  # noqa: E402


@pytest.mark.parametrize(
    "value, expected",
    [([0, 10], None), ((2, 5), [2, 5]), ([2.0, 50], [2, 10]), (None, None), ("x", None), (["a", 3], None), ([1], None)],
)
def test_time_frame_window_is_read_in_one_place(value, expected):
    assert ak.time_frame_window(value, 10) == expected


@pytest.mark.parametrize(
    "arguments, expected",
    [
        (("c",), ["c"]),
        (("c", "activity_extended"), ["c", "activity_extended"]),
        (("c", ak.ACTIVITY, [0, 5]), ["c", ak.ACTIVITY, [0, 5]]),
        (("c", "x", [0, 5]), ["c", "x", [0, 5]]),
    ],
)
def test_lcm_log_arguments_leave_out_trailing_defaults(arguments, expected):
    assert ak.lcm_log_arguments(*arguments) == expected


def test_lcm_log_arguments_give_the_same_log_as_the_direct_call():
    log = _log(40)
    for arguments in [(ak.CASE_ID,), (ak.CASE_ID, "lifecycle_transition"), (ak.CASE_ID, ak.ACTIVITY, [0, 5])]:
        direct = ak.to_lcm_log(log, *arguments)
        assert ak.to_lcm_log(log, *ak.lcm_log_arguments(*arguments)).equals(direct)


def test_kept_controls_are_the_four_that_do_not_depend_on_the_activity_column():
    value = {
        "activities": ["a"], "map_type": "sequence_based", "case_notion": "offer", "allow_loops": True, "show_empty": True, "folds": [],
    }
    assert kit.kept_controls_of(value) == {
        "map_type": "sequence_based", "case_notion": "offer", "allow_loops": True, "show_empty": True,
    }
    assert tuple(kit.kept_controls_of(value)) == kit.KEPT_CONTROLS


def test_kept_controls_overlay_the_draft_settings():
    draft = kit.normalise_settings({"activities": ["a"], "case_notion": "application"})
    kept = kit.kept_controls_of({"map_type": "sequence_based", "case_notion": "offer", "allow_loops": True, "show_empty": True})
    merged = kit.normalise_settings({**draft, **kept})
    assert (merged["map_type"], merged["case_notion"], merged["allow_loops"], merged["show_empty"]) == ("sequence_based", "offer", True, True)
    assert merged["activities"] == ["a"]
