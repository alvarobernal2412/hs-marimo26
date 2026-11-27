"""The filter of the maps in `02` and `03`: the column filters of the event-log table, taken by Refresh visualization into the drawn
settings, and the map drawn from what they keep. Run as marimo runs a notebook as a script (`app.run`); a request of the table's
page is made as the frontend makes it (see tests/test_log_filter.py)."""
import ast
import importlib.util
import os
import sys
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"
sys.path.insert(0, str(NOTEBOOKS / "lib"))
sys.path.insert(0, str(NOTEBOOKS))
import initial_analysis_kit as ak  # noqa: E402

pytest.importorskip("lcm")
pytest.importorskip("marimo")
DHANA = NOTEBOOKS / ak.DHANA


def _app(name):
    warnings.filterwarnings("ignore")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_").removesuffix(".py"), NOTEBOOKS / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def _run(app, defs=None):
    before = Path.cwd()
    os.chdir(NOTEBOOKS)  # as `marimo run` starts it: the notebook finds its files next to itself
    try:
        outputs, defined = app.run(defs=defs) if defs else app.run()
    finally:
        os.chdir(before)
    return " ".join(str(getattr(o, "text", "")) for o in outputs), defined


def _cell_of(name, notebook):
    """The names the cell that defines `name` defines (its top-level assignments, not the private `_` ones): overriding one of them
    in `app.run(defs=...)` means giving them all."""
    for node in ast.parse((NOTEBOOKS / notebook).read_text(encoding="utf8")).body:
        if not isinstance(node, ast.FunctionDef):
            continue
        names = []
        for statement in node.body:
            if isinstance(statement, ast.Assign):
                for target in statement.targets:
                    for leaf in (target.elts if isinstance(target, ast.Tuple) else [target]):
                        if isinstance(leaf, ast.Name) and not leaf.id.startswith("_"):
                            names.append(leaf.id)
        if name in names:
            return names
    raise KeyError(name)


def _filter_the_table(table, filters):
    """A request of the table's page with these column filters, as the frontend sends it."""
    from marimo._plugins.ui._impl.table import SearchTableArgs
    from marimo._runtime.functions import Function

    payload = {"page_size": 5, "page_number": 0, "filters": {"type": "group", "operator": "and", "negate": False, "children": filters}}
    Function(name="search", arg_cls=SearchTableArgs, function=table._search)(payload)


def _with_drawn(defined, notebook, settings):
    """The defs of the cell that keeps the drawn settings, with the drawn settings replaced (what Refresh does)."""
    names = _cell_of("get_drawn", notebook)
    return {**{n: defined[n] for n in names}, "get_drawn": lambda: settings}


def test_02_refresh_takes_the_table_filters_and_draws_from_what_they_keep():
    app = _app("02_lecture-process-map.py")
    text, first = _run(app)
    assert first["drawn_filter"] == [] and first["map_meta"]["cases"] == 1050 and "Filter:" not in text
    cases = sorted(first["event_log"][ak.CASE_ID].unique())[:3]
    _filter_the_table(first["event_table"], ak.case_filter(cases))
    first["refresh_button"]._on_click(0)  # Refresh: the drawn settings carry the table's filter
    settings = first["get_drawn"]()
    assert settings["filter"] == ak.case_filter(cases)
    text, after = _run(app, _with_drawn(first, "02_lecture-process-map.py", settings))
    assert after["map_log"][ak.CASE_ID].nunique() == after["map_meta"]["cases"] == 3
    assert "case_concept_name is one of" in text and "3 of 1,050 cases are kept" in text


@pytest.mark.skipif(not DHANA.is_file(), reason="the Dhana log is not public and is not here")
def test_03_the_filter_is_a_recorded_step_kept_after_a_reload_until_the_table_is_filtered(tmp_path, monkeypatch):
    monkeypatch.setenv("PMPROV_SYNC_URL", "")
    monkeypatch.setenv("PMPROV_DIR", str(tmp_path / "provenance"))
    notebook = "03_assignment-process-map.py"

    def steps(defined):
        return [node.operation.name for node in defined["adapter"].get_tree().nodes.values()]

    # no filter: no filter step, as before the filter existed
    text, first = _run(_app(notebook))
    assert "filter_log" not in steps(first) and first["drawn_filter"] == [] and "Filter:" not in text
    cases = sorted(first["event_log"][ak.CASE_ID].unique())[:3]

    # Refresh takes the table's filters only once the table was filtered in this session (outside a running notebook the page's
    # requests do not reach the watch, so the mark is set here as the watch sets it)
    table = first["event_table"]
    _filter_the_table(table, ak.case_filter(cases))
    first["refresh_button"]._on_click(0)
    assert first["get_drawn"]()["filter"] == []  # not filtered in this session: the drawn filter is kept
    table._filtered_here = True
    first["refresh_button"]._on_click(0)
    settings = first["get_drawn"]()
    assert settings["filter"] == ak.case_filter(cases)

    # the map is drawn from what the filter keeps, and the filter is a recorded step
    text, drawn = _run(_app(notebook), _with_drawn(first, notebook, settings))
    assert drawn["map_meta"]["cases"] == drawn["map_log"][ak.CASE_ID].nunique() == 3
    assert steps(drawn).count("filter_log") == 1 and steps(drawn)[-1] == "draw_map"
    assert "case_concept_name is one of" in text

    # opened again: the map is drawn with the recorded filter, nothing is recorded again, and the page offers to clear it
    text, again = _run(_app(notebook))
    assert again["drawn_filter"] == ak.case_filter(cases) and again["map_meta"]["cases"] == 3
    assert steps(again) == steps(drawn)
    assert "Clear filter" in text and "The table does not show this filter after a reload" in text
