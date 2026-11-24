import sys
import types
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notebooks" / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notebooks"))
import initial_analysis_kit as ak  # noqa: E402
from tracker.runtime import _param_fingerprint  # noqa: E402


def test_as_recorded_earlier_removes_the_added_columns_everywhere():
    value = {"standard": ["a", "lifecycle_state", "b"], "n": 3, "nested": {"x": ("lifecycle_state", "c")}}
    assert ak._as_recorded_earlier(value) == {"standard": ["a", "b"], "n": 3, "nested": {"x": ("c",)}}


def test_as_recorded_earlier_drops_the_added_columns_as_dict_keys():
    assert ak._as_recorded_earlier({"lifecycle_state": 1, "a": 2}) == {"a": 2}


def test_as_recorded_earlier_leaves_a_data_frame_untouched():
    frame = pd.DataFrame({"a": [1]})
    assert ak._as_recorded_earlier(frame) is frame


def _fake_runtime(stored_args):
    stored = {"func_name": "f", "param_fingerprint": _param_fingerprint(stored_args, {}), "output_state_id": "S1"}
    traced = []

    def trace_step(**kwargs):
        traced.append(kwargs)
        return "result"

    storage = types.SimpleNamespace(load_child_steps=lambda at: [stored] if at == "root" else [])
    rt = types.SimpleNamespace(_root_state_id="root", storage=storage, trace_step=trace_step, _current_state_id="NEW")
    return rt, traced


def f(columns):
    return list(columns)


def test_a_step_stored_before_the_added_column_is_matched():
    rt, traced = _fake_runtime([["a", "b"]])
    record, state_of = ak.analyst_recorder(rt, None)
    assert record(["out"], f, ["a", "lifecycle_state", "b"]) == ["a", "lifecycle_state", "b"]
    assert traced == []
    assert state_of("out") == "S1"


def test_a_step_that_differs_by_something_else_is_recorded():
    rt, traced = _fake_runtime([["a", "b"]])
    record, state_of = ak.analyst_recorder(rt, None)
    record(["out"], f, ["a", "x", "b"])
    assert len(traced) == 1
    assert state_of("out") == "NEW"
