import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notebooks" / "lib"))
import initial_analysis_kit as ak  # noqa: E402


def test_lifecycle_states_are_on_or_off_and_unknown_ones_are_missing():
    values = ["start", "resume", "complete", "suspend", "schedule", "withdraw", "ate_abort", "other", None]
    log = pd.DataFrame({"concept_name": ["a"] * 9, "lifecycle_transition": values})
    out = ak.add_lifecycle_state(log)
    assert out[ak.LIFECYCLE_STATE].tolist()[:7] == ["on", "on", "off", "off", "off", "off", "off"]
    assert out[ak.LIFECYCLE_STATE].isna().tolist()[7:] == [True, True]
    assert str(out[ak.LIFECYCLE_STATE].dtype) == "string"


def test_lifecycle_state_sits_right_after_the_transition():
    log = pd.DataFrame({"a": [1], "lifecycle_transition": ["start"], "z": [2]})
    assert list(ak.add_lifecycle_state(log).columns) == ["a", "lifecycle_transition", "lifecycle_state", "z"]


def test_a_log_without_a_lifecycle_or_with_a_state_is_unchanged():
    plain = pd.DataFrame({"a": [1]})
    assert ak.add_lifecycle_state(plain).equals(plain)
    done = pd.DataFrame({"lifecycle_transition": ["start"], "lifecycle_state": ["mine"]})
    assert ak.add_lifecycle_state(done).equals(done)


def test_normalise_log_adds_the_extended_activity_and_the_state():
    log = pd.DataFrame({"concept:name": ["a"], "lifecycle:transition": ["complete"]})
    out = ak.normalise_log(log)
    assert out["activity_extended"].tolist() == ["a_complete"]
    assert out["lifecycle_state"].tolist() == ["off"]
    assert list(out.columns)[-1] == "activity_extended"


def _events():
    return pd.DataFrame(
        {
            "case": ["c1", "c1", "c2"],
            "act": ["a", "b", "a"],
            "t": pd.to_datetime(["2024-01-01 10:00", "2024-01-01 12:30", "2024-01-02 09:00"]),
        }
    )


def test_case_log_has_the_duration_after_the_end_time():
    cases = ak.build_case_log(_events(), "case", "act", "t", [])
    assert list(cases.columns)[:4] == ["start_time", "end_time", "duration", "no_of_events"]
    assert cases.loc["c1", "duration"] == pd.Timedelta("2h30m")


def test_enrichment_code_can_use_the_duration():
    code = "case_log['hours'] = case_log['duration'].dt.total_seconds() / 3600"
    cases = ak.build_case_log(_events(), "case", "act", "t", [], code)
    assert cases.loc["c1", "hours"] == 2.5
