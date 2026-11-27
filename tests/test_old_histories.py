"""Work saved with the 1.x releases opens with this version: a map-explorer history recorded with the call shapes of 1.0-1.2 and of
1.3 (on the public Sepsis log, with a figure as linear-continuous-process-mapper 0.1.0 drew it: no `meta`, no traces), re-opened
the way `03` re-opens it. Nothing is recorded again, the settings, the arrangement and the annotations come back, old anchors still
mark their node or link, the panel lists them and exports a report.

The end-to-end check with the released notebooks in the student runtime (and the real Dhana log) is a script outside the tests:
see `.superpowers/sdd/process-map-tutorial/compat-report.md`."""
import json
import sys
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "notebooks" / "lib"))
sys.path.insert(0, str(ROOT / "notebooks"))
import bpm_kit as kit  # noqa: E402
import initial_analysis_kit as ak  # noqa: E402

pytest.importorskip("lcm")
pytest.importorskip("provenance_widget")
warnings.filterwarnings("ignore", message=r"init_marimo\(\) was called but patch_marimo_ast_compile")
SEPSIS = ROOT / "notebooks" / "data" / "SepsisCases2020EventLog.xes"
ROOM = (100, 140, 110)
CUSTOM_COLUMN = "org_group"  # another activity column of the Sepsis log (1.3 let the student choose one)


def load_event_log(name):
    """The step `03` records first (the name of the file, here the public Sepsis log)."""
    return ak.load_log(ROOT / "notebooks" / name)


def _old_draw_map(log, activities, map_type, allow_loops, show_empty, folds, case_notion, height=620, room=(10, 10, 10)):
    """`kit.draw_map` as 1.x drew a map (its signature, so the tracker records the same parameter names):
    linear-continuous-process-mapper 0.1.0 put no traces in the figure or the metadata."""
    figure, meta = kit.draw_map(log, activities, map_type, allow_loops, show_empty, folds, case_notion, height, room)
    figure.data[0].meta = None
    return figure, {k: v for k, v in meta.items() if k not in ("trace_count", "traces_truncated")}


def _tracker(folder, fresh):
    from tracker import init_marimo

    (folder / "artifacts").mkdir(parents=True, exist_ok=True)
    return init_marimo(
        history_name=ak.MAP_EXPLORER_HISTORY_NAME, branch_name="main", db_path=str(folder / "provenance.db"),
        artifact_dir=str(folder / "artifacts"), fresh=fresh,
    )


def _steps(rt):
    return [step["func_name"] for step in ak._stored_steps(rt)]


def _record_old(folder, shape):
    """A history as 1.x recorded it: maps (the last one dragged) and annotations on the map, a node and a link."""
    from provenance_widget import arrangement
    from provenance_widget.pmprov_adapter import PmprovAdapter

    rt = _tracker(folder, fresh=True)
    adapter = PmprovAdapter(rt)
    record, state_of = ak.analyst_recorder(rt, adapter)
    name = str(SEPSIS.relative_to(ROOT / "notebooks")).replace("\\", "/")
    log = record(["event_log"], load_event_log, name)
    top5 = sorted(log[ak.ACTIVITY].value_counts().index[:5])

    def draw(activities, map_type, column=ak.ACTIVITY, window=None, folds=None, loops=True, empty=True):
        args = [ak.CASE_ID] if shape == "1.0" else [ak.CASE_ID, column, window][: 3 if window else (2 if column != ak.ACTIVITY else 1)]
        lcm_log = record(["lcm_log"], ak.to_lcm_log, log, *args)
        return record(["map_figure", "map_meta"], _old_draw_map, lcm_log, activities, map_type, loops, empty, folds or {},
                      "application", 900, room=ROOM, name="draw_map")

    draw(top5, "last_activity_based", loops=False, folds={"Two": top5[:2]})
    if shape.startswith("1.3"):
        draw(top5, "set_based", window=[0, 200])
    if shape == "1.3-custom":  # the last map with every setting away from its default: they must come back
        acts = sorted(log[CUSTOM_COLUMN].value_counts().index[:4])
        figure, _ = draw(acts, "last_activity_based", column=CUSTOM_COLUMN, window=[0, 200], folds={"Two": acts[:2]}, loops=False,
                         empty=False)
    else:
        figure, _ = draw(top5, "set_based")
    n = len(figure.data[0].node.label)
    positions = json.dumps([{"x": [round(0.05 + 0.9 * i / (n - 1), 4) for i in range(n)], "y": [0.5] * n}])
    record(["arranged_map"], arrangement.arranged, figure, positions, name="arrange_map")
    shown = state_of("arranged_map")
    sankey = figure.data[0]
    labels = list(sankey.node.label)
    link = max(range(len(sankey.link.source)), key=lambda i: sankey.link.value[i])
    pins = [
        ("chart_selection", None),
        ("node", labels[1]),
        ("link", f"{labels[sankey.link.source[link]]} -> {labels[sankey.link.target[link]]} ({sankey.link.label[link]})"),
    ]
    for granularity, detail in pins:
        ref = {"artifactId": shown, "artifactName": "process_map", "granularity": granularity}
        if detail is not None:
            ref["detail"] = detail
        adapter.persist_annotation(shown, {"note": f"About the {granularity}.", "tags": [{"name": "finding"}], "artifacts": [ref]})
    rt.storage._executor.submit(lambda: None).result()
    return name, pins


def _reopen_as_03(folder, name):
    """What the new `03` records when it is opened again on this history (its cells, in order, without the page)."""
    from provenance_widget import arrangement
    from provenance_widget.pmprov_adapter import PmprovAdapter

    rt = _tracker(folder, fresh=False)
    adapter = PmprovAdapter(rt)
    record, state_of = ak.analyst_recorder(rt, adapter)
    log = record(["event_log"], load_event_log, name)
    recorded = ak.params_at(adapter, None, "to_lcm_log") or {}
    activity = recorded.get("activity_column") or ak.ACTIVITY
    frame = ak.time_frame(log, ak.CASE_ID, ak.TIMESTAMP)
    window = ak.time_frame_window(recorded.get("window"), frame["stop"])
    settings = kit.normalise_settings({**kit.last_map_settings(adapter), "activity_column": activity, "time_frame": window,
                                       "filter": ak.last_filter(adapter)})
    map_log, _ = ak.record_filter(record, adapter, log, settings["filter"], {})
    origin = ak.window_origin(frame) if map_log is not log else None
    lcm_log = record(["lcm_log"], ak.to_lcm_log, map_log, *ak.lcm_log_arguments(ak.CASE_ID, activity, window, origin))
    figure, meta = record(["map_figure", "map_meta"], kit.draw_map, lcm_log, settings["activities"], settings["map_type"],
                          settings["allow_loops"], settings["show_empty"], settings["folds"], "application", 900, room=ROOM)
    positions = kit.last_arrangement(adapter, state_of("map_figure"))
    if positions:
        record(["arranged_map"], arrangement.arranged, figure, positions, name="arrange_map")
    rt.storage._executor.submit(lambda: None).result()
    return rt, adapter, settings, positions


def test_the_settings_of_an_old_map_come_back_as_they_were_left(tmp_path):
    """Activity column, time frame, fold, abstraction, self-loops and empty traces of the last map of a 1.3 history."""
    name, _ = _record_old(tmp_path, "1.3-custom")
    before = _steps(_tracker(tmp_path, fresh=False))
    _, _, settings, positions = _reopen_as_03(tmp_path, name)
    assert _steps(_tracker(tmp_path, fresh=False)) == before
    assert settings["activity_column"] == CUSTOM_COLUMN and settings["time_frame"] == [0, 200]
    assert settings["map_type"] == "last_activity_based" and settings["allow_loops"] is False and settings["show_empty"] is False
    assert list(settings["folds"]) == ["Two"] and positions


@pytest.mark.parametrize("shape", ["1.0", "1.3"])
def test_an_old_map_history_opens_without_recording_again(tmp_path, shape):
    name, _ = _record_old(tmp_path, shape)
    before = _steps(_tracker(tmp_path, fresh=False))
    _, adapter, settings, positions = _reopen_as_03(tmp_path, name)
    after = _steps(_tracker(tmp_path, fresh=False))
    assert after == before, (before, after)  # no filter step, no second map, no arrangement without a drag
    assert "filter_log" not in after and settings["filter"] == []
    assert settings["map_type"] == "set_based" and settings["folds"] == {} and positions  # the last map, as it was left


@pytest.mark.parametrize("shape", ["1.0", "1.3"])
def test_old_annotations_are_listed_exported_and_still_mark_their_node_and_link(tmp_path, shape):
    from provenance_widget.pmprov_adapter import PmprovAdapter
    from provenance_widget.report_targets import mark_sankey
    from provenance_widget.widget import ProvenancePanel

    name, pins = _record_old(tmp_path, shape)
    rt, adapter, _, _ = _reopen_as_03(tmp_path, name)
    panel = ProvenancePanel(source=PmprovAdapter(rt), mode="analyst", auto_refresh=False)
    listed = [a for node in panel.widget.tree["nodes"].values() for a in node.get("annotations") or []]
    assert sorted((r["granularity"], r.get("detail")) for a in listed for r in a["artifacts"]) == sorted(pins, key=str)
    assert panel.export_pdf()[:4] == b"%PDF"
    for state, node in adapter.get_tree().nodes.items():
        for annotation in node.annotations:
            figure = adapter.snapshot(state, ["arranged_map"])["arranged_map"]
            assert getattr(figure.data[0], "meta", None) is None and kit.traces_of(figure) == []  # an lcm 0.1.0 figure
            for ref in annotation.artifacts:
                if ref.granularity in ("node", "link"):
                    assert mark_sankey(figure, ref.granularity, ref.detail)[1], (ref.granularity, ref.detail)


def test_new_work_on_an_old_history_is_kept_with_the_old(tmp_path):
    from provenance_widget.pmprov_adapter import PmprovAdapter

    name, pins = _record_old(tmp_path, "1.3")
    rt, adapter, _, _ = _reopen_as_03(tmp_path, name)
    record, state_of = ak.analyst_recorder(rt, adapter)
    log = record(["event_log"], load_event_log, name)
    lcm_log = record(["lcm_log"], ak.to_lcm_log, log, ak.CASE_ID)
    record(["map_figure", "map_meta"], kit.draw_map, lcm_log, None, "set_based", True, True, {}, "application", 900, room=ROOM)
    state = state_of("map_figure")
    adapter.persist_annotation(state, {"note": "New.", "tags": [{"name": "finding"}],
                                       "artifacts": [{"artifactId": state, "artifactName": "process_map", "granularity": "chart_selection"}]})
    rt.storage._executor.submit(lambda: None).result()
    again = PmprovAdapter(_tracker(tmp_path, fresh=False))
    notes = [a.note for node in again.get_tree().nodes.values() for a in node.annotations]
    assert sorted(notes) == sorted([f"About the {g}." for g, _ in pins] + ["New."])
