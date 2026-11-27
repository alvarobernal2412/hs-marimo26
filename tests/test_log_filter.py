"""The filter on the event log of the process maps: the column filters of the log's table, what they keep, and that they come back
from a recorded step."""
import json
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notebooks" / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notebooks"))
import initial_analysis_kit as ak  # noqa: E402

mo = pytest.importorskip("marimo")


def _log():
    return pd.DataFrame(
        {
            ak.CASE_ID: ["c1", "c1", "c2", "c2", "c3", "c3"],
            ak.ACTIVITY: ["a", "b", "a", "c", "a", "b"],
            ak.TIMESTAMP: pd.date_range("2024-01-01", periods=6, freq="h"),
        }
    )


def _request(filters=None, query=None):
    """A request of the table's page, as the frontend sends it (plain JSON)."""
    payload = {"page_size": 5, "page_number": 0}
    if filters is not None:
        payload["filters"] = {"type": "group", "operator": "and", "negate": False, "children": filters}
    if query is not None:
        payload["query"] = query
    return payload


def _search(table, payload):
    """The table's search, called as marimo's runtime calls it for a request of the page: through a `Function`, which parses the
    plain payload into marimo's own `SearchTableArgs` (with `FilterGroup` and `FilterCondition`)."""
    from marimo._plugins.ui._impl.table import SearchTableArgs
    from marimo._runtime.functions import Function

    return Function(name="search", arg_cls=SearchTableArgs, function=table._search)(payload)


# --- marimo's internals -----------------------------------------------------------------------------------------------------------


def test_the_marimo_internals_the_filter_relies_on_exist():
    """`ak._marimo_filters` names private parts of marimo 0.25.2; a marimo without one of them must fail here, loudly."""
    parts = ak._marimo_filters()
    assert all(parts.values()), parts
    table = mo.ui.table(_log())
    assert hasattr(table, "_current_filters") and hasattr(table, "_search")


# --- the table's filters --------------------------------------------------------------------------------------------------------


def test_table_filters_are_the_conditions_the_page_sent():
    table = mo.ui.table(_log(), page_size=5)
    assert ak.table_filters(table) == []
    _search(table, _request(ak.case_filter(["c3", "c1"])))
    assert ak.table_filters(table) == ak.case_filter(["c3", "c1"])
    assert json.loads(json.dumps(ak.table_filters(table))) == ak.table_filters(table)


def test_filter_log_keeps_what_the_table_shows():
    log = _log()
    table = mo.ui.table(log, page_size=5)
    _search(table, _request(ak.case_filter(["c3", "c1"])))
    from marimo._utils.narwhals_utils import unwrap_narwhals_dataframe

    shown = unwrap_narwhals_dataframe(table._searched_manager.data)
    kept = ak.filter_log(log, ak.table_filters(table))
    assert list(kept[ak.CASE_ID]) == list(shown[ak.CASE_ID]) == ["c1", "c1", "c3", "c3"]
    pd.testing.assert_frame_equal(kept[log.columns].reset_index(drop=True), shown[log.columns].reset_index(drop=True))


def test_the_search_box_is_no_filter():
    table = mo.ui.table(_log(), page_size=5)
    _search(table, _request(query="c1"))
    assert ak.table_filters(table) == []


def test_cleared_filters_are_no_filter():
    table = mo.ui.table(_log(), page_size=5)
    _search(table, _request(ak.case_filter(["c1"])))
    _search(table, _request())
    assert ak.table_filters(table) == []


def test_a_group_that_is_not_a_plain_and_is_kept_whole():
    table = mo.ui.table(_log(), page_size=5)
    payload = _request(ak.case_filter(["c1"]) + ak.case_filter(["c2"]))
    payload["filters"]["operator"] = "or"
    _search(table, payload)
    filters = ak.table_filters(table)
    assert len(filters) == 1 and filters[0]["type"] == "group" and filters[0]["operator"] == "or"
    assert sorted(ak.filter_log(_log(), filters)[ak.CASE_ID].unique()) == ["c1", "c2"]


# --- the filter as data ---------------------------------------------------------------------------------------------------------


def test_case_filter_is_one_condition():
    assert ak.case_filter(["c3", "c1"]) == [
        {"type": "condition", "column_id": ak.CASE_ID, "operator": "in", "value": ["c3", "c1"], "negate": False}
    ]
    assert ak.case_filter(["a"], column=ak.ACTIVITY)[0]["column_id"] == ak.ACTIVITY


def test_filter_log_keeps_only_the_cases_of_a_case_filter():
    log = _log()
    kept = ak.filter_log(log, ak.case_filter(["c3", "c1"]))
    assert isinstance(kept, pd.DataFrame)
    assert sorted(kept[ak.CASE_ID].unique()) == ["c1", "c3"] and len(kept) == 4
    assert len(log) == 6  # the log itself is not changed


def test_filter_log_without_a_filter_is_the_same_frame():
    log = _log()
    assert ak.filter_log(log, []) is log
    assert ak.filter_log(log, "[]") is log
    assert ak.filter_log(log, ak.case_filter(["c1"], column="no such column")) is log  # the table drops it too


def test_filter_log_does_not_change_the_filter():
    filters = ak.case_filter(["c1"])
    before = json.dumps(filters)
    ak.filter_log(_log(), filters)
    assert json.dumps(filters) == before


def test_filter_log_of_two_conditions_and_a_negated_one():
    filters = [
        {"type": "condition", "column_id": ak.ACTIVITY, "operator": "equals", "value": "a", "negate": False},
        {"type": "condition", "column_id": ak.CASE_ID, "operator": "equals", "value": "c2", "negate": True},
    ]
    assert list(ak.filter_log(_log(), filters)[ak.CASE_ID]) == ["c1", "c3"]


def test_filter_words_of_a_case_filter():
    assert ak.filter_words(ak.case_filter(["c3", "c1"])) == "case_concept_name is one of c3, c1"
    assert ak.filter_words(ak.filter_text(ak.case_filter(["c3"]))) == "case_concept_name is one of c3"
    assert ak.filter_words([]) == ""


def test_filter_words_of_two_conditions_and_a_group():
    filters = [
        {"type": "condition", "column_id": "concept_name", "operator": "equals", "value": "A", "negate": False},
        {"type": "condition", "column_id": "cost", "operator": ">=", "value": 10, "negate": True},
        {"type": "group", "operator": "or", "negate": False, "children": ak.case_filter(["c1"]) + ak.case_filter(["c2"])},
    ]
    assert ak.filter_words(filters) == (
        "concept_name is A and not (cost >= 10) and (case_concept_name is one of c1 or case_concept_name is one of c2)"
    )


def test_filter_problem_of_an_empty_result():
    log = _log()
    problem = ak.filter_problem(log, ak.filter_log(log, ak.case_filter(["nobody"])))
    assert problem and "no event" in problem


def test_filter_problem_of_a_missing_column():
    log = _log().assign(resource=["r"] * 6)
    assert ak.ACTIVITY in ak.filter_problem(log, log.drop(columns=[ak.ACTIVITY]))
    assert "resource" in ak.filter_problem(log, log.drop(columns=["resource"]), needed=["resource"])


def test_filter_problem_of_a_time_column_that_is_no_time():
    log = _log()
    assert ak.TIMESTAMP in ak.filter_problem(log, log.assign(**{ak.TIMESTAMP: "x"}))


def test_no_filter_problem_for_a_kept_case():
    log = _log()
    assert ak.filter_problem(log, ak.filter_log(log, ak.case_filter(["c2"]))) is None
    assert ak.filter_problem(log, log) is None


# --- the recorded filter --------------------------------------------------------------------------------------------------------


def _adapter(*steps):
    nodes = {f"S{i}": types.SimpleNamespace(operation=types.SimpleNamespace(name=name), params=params) for i, (name, params) in enumerate(steps)}
    return types.SimpleNamespace(get_tree=lambda: types.SimpleNamespace(nodes=nodes))


def test_last_filter_of_a_history_without_one():
    assert ak.last_filter(_adapter(("load_event_log", {"name": "x"}), ("draw_map", {}))) == []


def test_last_filter_is_the_latest_filter_step():
    first, second = ak.case_filter(["c1"]), ak.case_filter(["c2"])
    adapter = _adapter(
        ("filter_log", {"filters": ak.filter_text(first)}), ("draw_map", {}), ("filter_log", {"filters": ak.filter_text(second)})
    )
    assert ak.last_filter(adapter) == second


def test_a_long_filter_comes_back_whole():
    """The tracker keeps a list argument 50 items long and a few levels deep: the step records the filter as text."""
    cases = [f"c{i}" for i in range(80)]
    text = ak.filter_text(ak.case_filter(cases))
    assert isinstance(text, str)
    assert ak.last_filter(_adapter(("filter_log", {"filters": text}))) == ak.case_filter(cases)
    assert len(ak.filter_log(_log(), text)) == len(ak.filter_log(_log(), ak.case_filter(cases))) == 6


def test_last_filter_of_a_damaged_step_is_no_filter():
    assert ak.last_filter(_adapter(("filter_log", {"filters": "not json"}))) == []
    assert ak.last_filter(_adapter(("filter_log", {"filters": '{"a": 1}'}))) == []
    assert ak.last_filter(_adapter(("filter_log", {"filters": ["text"]}))) == []


def test_recorded_filter_at_a_step_is_the_last_filter_before_it():
    """What a reviewer sees at a step: the filter recorded at or before it, not the latest of the history."""
    first, second = ak.case_filter(["c1"]), ak.case_filter(["c2"])
    adapter = _adapter(
        ("choose_log", {"name": "a"}), ("load_log", {"name": "a"}), ("filter_log", {"filters": ak.filter_text(first)}),
        ("draw_map", {}), ("filter_log", {"filters": ak.filter_text(second)}), ("draw_map", {}),
    )
    assert [ak.recorded_filter_at(adapter, f"S{i}") for i in range(6)] == [[], [], first, first, second, second]


def test_recorded_filter_at_ends_where_another_log_is_chosen():
    adapter = _adapter(
        ("choose_log", {"name": "a"}), ("filter_log", {"filters": ak.filter_text(ak.case_filter(["c1"]))}),
        ("choose_log", {"name": "b"}), ("load_log", {"name": "b"}), ("draw_map", {}),
    )
    assert ak.recorded_filter_at(adapter, "S1") == ak.case_filter(["c1"])
    assert [ak.recorded_filter_at(adapter, f"S{i}") for i in (2, 3, 4)] == [[], [], []]


def test_recorded_filter_at_a_state_that_is_no_step_is_no_filter():
    """The start of a replay, before the first step, is not a node of the tree."""
    adapter = _adapter(("filter_log", {"filters": ak.filter_text(ak.case_filter(["c1"]))}))
    assert ak.recorded_filter_at(adapter, "__initial__") == []
    assert ak.recorded_filter_at(adapter, None) == []


def test_made_before_the_log_was_chosen():
    """What a step made for a log chosen earlier is not shown with a log chosen later (the toy map with the Sepsis log)."""
    adapter = _adapter(
        ("choose_log", {}), ("load_log", {}), ("draw_map", {}), ("choose_log", {}), ("load_log", {}), ("draw_map", {}),
    )
    assert [ak.made_before_choice(adapter, f"S{i}", "load_log") for i in range(6)] == [False, False, False, True, False, False]
    assert [ak.made_before_choice(adapter, f"S{i}", "draw_map") for i in range(6)] == [False, False, False, True, True, False]
    assert ak.made_before_choice(adapter, "__initial__", "draw_map") is False


# --- the time frame of a filtered log -----------------------------------------------------------------------------------------


def _days_log():
    # three cases of one day each, a day apart: c1 on day 0, c2 on day 2, c3 on day 4
    days = [0, 0, 2, 2, 4, 4]
    return _log().assign(**{ak.TIMESTAMP: [pd.Timestamp("2024-01-01") + pd.Timedelta(d, "D") + pd.Timedelta(h, "h") for d, h in zip(days, [0, 1] * 3)]})


def test_the_time_frame_of_a_filtered_log_counts_from_the_whole_log():
    """The slider is built from the whole log: a window of a filtered log counts from the start of the whole log, not of what is left."""
    log = _days_log()
    origin = ak.window_origin(ak.time_frame(log, ak.CASE_ID, ak.TIMESTAMP))
    assert json.loads(json.dumps(origin)) == origin
    filtered = ak.filter_log(log, ak.case_filter(["c2", "c3"]))
    window = [2, 3]  # day 2 to day 3 of the whole log: c2 only
    assert ak.cases_in_time_frame(filtered, window, origin) == (1, 2)
    assert sorted(ak.to_lcm_log(filtered, ak.CASE_ID, ak.ACTIVITY, window, origin)["case:concept:name"].unique()) == ["c2"]
    # counted from the filtered log's own start (day 2) the window would be day 4 to 5: another case
    assert list(ak.to_lcm_log(filtered, ak.CASE_ID, ak.ACTIVITY, window)["case:concept:name"].unique()) == ["c3"]


def test_lcm_log_arguments_name_the_origin_only_for_a_window():
    origin = {"start": "2024-01-01 00:00:00", "unit": "D"}
    assert ak.lcm_log_arguments(ak.CASE_ID, ak.ACTIVITY, None, origin) == [ak.CASE_ID]
    assert ak.lcm_log_arguments(ak.CASE_ID, ak.ACTIVITY, [1, 2], origin) == [ak.CASE_ID, ak.ACTIVITY, [1, 2], origin]
    assert ak.lcm_log_arguments(ak.CASE_ID, ak.ACTIVITY, [1, 2]) == [ak.CASE_ID, ak.ACTIVITY, [1, 2]]


# --- "filtered in this session": a reopened 03 keeps its recorded filter until the table is filtered ----------------------------


class _CellContext:
    """What marimo's kernel gives a running cell, as far as a table needs it, with marimo's own function registry: the page's requests
    reach the table through it."""

    def __init__(self):
        from marimo._plugins.ui._core.ids import IDProvider
        from marimo._runtime.functions import FunctionRegistry

        self._ids = IDProvider("cell")
        self.function_registry = FunctionRegistry()
        self.ui_element_registry = types.SimpleNamespace(register=lambda *a: None, delete=lambda *a: None)
        self.execution_context = None
        self.virtual_file_registry = types.SimpleNamespace(filenames=lambda: [], reference=lambda *a: None, dereference=lambda *a: None)

    def take_id(self):
        return self._ids.take_id()

    def get_ui_initial_value(self, object_id):
        raise KeyError(object_id)


@pytest.fixture
def cell(monkeypatch):
    import marimo._plugins.ui._core.ui_element as ui_element
    import marimo._runtime.context as context

    running = _CellContext()
    monkeypatch.setattr(ui_element, "get_context", lambda: running)
    monkeypatch.setattr(context, "get_context", lambda: running)
    return running


def _page(cell, table, payload):
    """A request of the page for `table`, through the function marimo registered for it (what the runtime calls)."""
    return cell.function_registry.get_function(table._id, "search")(payload)


def test_a_table_is_marked_once_the_page_filters_it_and_stays_marked(cell):
    table = ak.watch_filters(mo.ui.table(_log(), page_size=5))
    assert ak.table_was_filtered(table) is False
    _page(cell, table, _request())  # the page asks for rows without a filter: not filtered
    _page(cell, table, _request(query="c1"))  # the search box is no filter
    assert ak.table_was_filtered(table) is False
    _page(cell, table, _request(ak.case_filter(["c2"])))
    assert ak.table_was_filtered(table) is True and ak.table_filters(table) == ak.case_filter(["c2"])
    _page(cell, table, _request())  # cleared again: still filtered in this session, and the filter is none
    assert ak.table_was_filtered(table) is True and ak.table_filters(table) == []


def test_watching_twice_wraps_once(cell):
    table = mo.ui.table(_log(), page_size=5)
    ak.watch_filters(ak.watch_filters(table))
    _page(cell, table, _request(ak.case_filter(["c2"])))
    assert ak.table_was_filtered(table)


def test_a_table_outside_a_running_notebook_is_never_marked():
    table = ak.watch_filters(mo.ui.table(_log(), page_size=5))
    _search(table, _request(ak.case_filter(["c2"])))
    assert ak.table_was_filtered(table) is False
