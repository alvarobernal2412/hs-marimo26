"""`04_tutorial-process-map.py` run at every step of the recorded tutorial, as the player moves it: what each part reads is the
log, the filter and the map of that step."""
import importlib.util
import os
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "04_tutorial-process-map.py"

pytest.importorskip("lcm")
pytest.importorskip("provenance_widget")


@pytest.fixture(scope="module")
def notebook():
    warnings.filterwarnings("ignore")
    before = Path.cwd()
    os.chdir(NOTEBOOK.parent)  # as `marimo run` starts it: the notebook finds its files next to itself
    try:
        spec = importlib.util.spec_from_file_location("tutorial_notebook", NOTEBOOK)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _, first = module.app.run()
        yield module.app, first
    finally:
        os.chdir(before)


def _cases_kept(filters, log_cases):
    """The cases a recorded case filter keeps (all of them without a filter)."""
    kept = {value for condition in filters for value in condition["value"]}
    return kept or set(log_cases)


def test_every_step_shows_its_own_log_filter_and_map(notebook):
    """At every step: the picker shows the log chosen then; the table shows that log as filtered at this step; the map is the last one
    drawn for this log, and the "Filter:" line above it names the filter that map was drawn from (which is not yet the filter of the
    table at a step that filters the log before its map is drawn)."""
    import html

    import initial_analysis_kit as ak
    from provenance_widget.snapshot import INITIAL_STATE

    app, first = notebook
    nodes = first["adapter"].get_tree().nodes
    fixed = {name: first[name] for name in ("rt", "adapter", "panel")}
    chosen, drawn_for = None, None
    current, drawn = [], []  # the filter of the table now, and the filter the shown map was drawn from
    differ = 0  # steps where the two differ: the case this test is about
    before = Path.cwd()
    os.chdir(NOTEBOOK.parent)
    try:
        for state in [INITIAL_STATE, *nodes]:
            outputs, defs = app.run(defs={**fixed, "get_cursor": (lambda s=state: s)})
            name = nodes[state].operation.name if state in nodes else None
            if name == "choose_log":
                chosen, current = nodes[state].params["name"], []
            elif name == "load_log":
                current = []
            elif name == "filter_log":
                current = ak._filters_from(nodes[state].params["filters"])
            elif name == "draw_map":
                drawn_for, drawn = chosen, current
            text = html.unescape(" ".join(str(getattr(o, "text", "")) for o in outputs))
            assert "Traceback" not in text
            assert defs.get("log_name") == chosen
            if "event_log" in defs:  # the table: the log as filtered at this step
                assert set(defs["map_log"][ak.CASE_ID]) == _cases_kept(current, defs["event_log"][ak.CASE_ID])
            shown = "No map of this log yet" not in text and isinstance(defs.get("map_meta"), dict)
            assert shown == (drawn_for is not None and drawn_for == chosen), state
            if not shown:
                continue
            # the map and its line: the filter of the step that drew it
            assert defs["drawn_filters"] == drawn
            assert defs["drawn_log"][ak.CASE_ID].nunique() == defs["map_meta"]["cases"]
            if drawn:
                assert f"Filter: {ak.filter_words(drawn)} · " in text.replace("<strong>", "").replace("</strong>", "")
            else:
                assert "Filter:" not in text
            if current != drawn:
                differ += 1
                if current:
                    assert f"{ak.filter_words(current)} · " not in text
    finally:
        os.chdir(before)
    assert chosen == "data/SepsisCases2020EventLog.xes"
    assert differ >= 3  # the steps that filter (and prepare) a map before it is drawn


def test_the_tutorial_opens_on_the_first_step(notebook):
    """A reviewer's panel starts on the latest step; the tutorial moves it to step 1, so it is read from the beginning."""
    _, first = notebook
    assert first["snap"].step == 1 and first["snap"].operation == "choose_log"
    assert first["log_name"] == "data/dfg-example.xes"

