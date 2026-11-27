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


def _adapter_of(*names):
    nodes = {f"S{i}": types.SimpleNamespace(operation=types.SimpleNamespace(name=n), params={}) for i, n in enumerate(names)}
    return types.SimpleNamespace(get_tree=lambda: types.SimpleNamespace(nodes=nodes))


def test_a_history_without_a_filter_step_records_no_filter():
    rt, traced = _fake_runtime([["a", "b"]])
    record, state_of = ak.analyst_recorder(rt, None)
    log = pd.DataFrame({ak.CASE_ID: ["c1"]})
    shown, recorded = ak.record_filter(record, _adapter_of("load_event_log", "draw_map"), log, [])
    assert shown is log and recorded is False
    assert traced == []
    record(["out"], f, ["a", "b"])  # and the stored step after it is still matched
    assert traced == [] and state_of("out") == "S1"


def test_a_filter_is_recorded_as_a_step():
    rt, traced = _fake_runtime([["a", "b"]])
    record, state_of = ak.analyst_recorder(rt, None)
    log = pd.DataFrame({ak.CASE_ID: ["c1", "c2"]})
    _, recorded = ak.record_filter(record, _adapter_of("load_event_log"), log, ak.case_filter(["c1"]))
    assert recorded is True
    assert [t["func_name"] for t in traced] == ["filter_log"]
    assert traced[0]["args"][1] == ak.filter_text(ak.case_filter(["c1"]))  # text: the tracker keeps it whole


def test_a_filter_that_is_removed_is_recorded_as_no_filter():
    """So that a notebook opened again does not bring back a filter the analyst removed."""
    rt, traced = _fake_runtime([["a", "b"]])
    record, _ = ak.analyst_recorder(rt, None)
    log = pd.DataFrame({ak.CASE_ID: ["c1"]})
    _, recorded = ak.record_filter(record, _adapter_of("load_event_log", "filter_log"), log, [])
    assert recorded is True
    assert [t["args"][1] for t in traced] == ["[]"]


def test_the_same_filter_again_is_not_recorded_again():
    """Every Refresh asks for the filter of the drawn settings; with the notebook's memo the same filter is one step only."""
    rt, traced = _fake_runtime([["a", "b"]])
    record, _ = ak.analyst_recorder(rt, None)
    log = pd.DataFrame({ak.CASE_ID: ["c1", "c2"]})
    memo = {}
    adapter = _adapter_of("load_event_log")
    first = ak.record_filter(record, adapter, log, ak.case_filter(["c1"]), memo)
    again = ak.record_filter(record, adapter, log, ak.case_filter(["c1"]), memo)
    assert again is first and len(traced) == 1
    ak.record_filter(record, adapter, log, ak.case_filter(["c2"]), memo)
    assert len(traced) == 2


def test_no_filter_with_a_memo_records_no_step():
    rt, traced = _fake_runtime([["a", "b"]])
    record, _ = ak.analyst_recorder(rt, None)
    log = pd.DataFrame({ak.CASE_ID: ["c1"]})
    shown, recorded = ak.record_filter(record, _adapter_of("load_event_log", "draw_map"), log, [], {})
    assert shown is log and recorded is False and traced == []
