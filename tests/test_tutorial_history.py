"""The recorded process map tutorial (`build/build_tutorial_history.py`) that `04_tutorial-process-map.py` replays."""
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

ZIP = ROOT / "notebooks" / kit.PROCESS_MAP_TUTORIAL_ZIP
TOY, SEPSIS = "data/dfg-example.xes", "data/SepsisCases2020EventLog.xes"
MAPS = [
    ("sequence_based", 1), ("sequence_based", 2), ("sequence_based", 3), ("sequence_based", 4),
    ("set_based", 4), ("last_activity_based", 4), ("last_activity_based", 1050), ("set_based", 1050),
]
KINDS = {"intent", "finding"}
TOPICS = {"sum-of-traces", "prefix-tree", "set-abstraction", "dfg", "mainstream", "knockout", "leakage", "rework", "ordering"}


@pytest.fixture(scope="module")
def recorded(tmp_path_factory):
    from provenance_widget.pmprov_adapter import PmprovAdapter
    from provenance_widget.portable import unpack_provenance
    from provenance_widget.widget import ProvenancePanel

    folder = tmp_path_factory.mktemp("tutorial") / "provenance"
    unpack_provenance(ZIP.read_bytes(), folder)
    rt = kit.open_recorded(folder, kit.PROCESS_MAP_TUTORIAL_HISTORY)
    assert rt is not None, "the zip has no history of that name"
    adapter = PmprovAdapter(rt)
    panel = ProvenancePanel(source=adapter, mode="reviewer", auto_refresh=False)
    nodes = adapter.get_tree().nodes
    return adapter, panel, nodes


def _steps(nodes, name):
    return [state for state, node in nodes.items() if node.operation.name == name]


def _annotations(nodes):
    return [(state, a) for state, node in nodes.items() for a in node.annotations]


def test_the_zip_is_shipped_and_small():
    assert ZIP.is_file()
    assert ZIP.stat().st_size < 5_000_000


def test_the_maps_in_order(recorded):
    adapter, panel, nodes = recorded
    found = []
    for state in _steps(nodes, "draw_map"):
        meta = panel.snapshot(state).get("map_meta")
        found.append((nodes[state].params["map_type"], meta["cases"]))
        assert meta["settings"].get("layout") == "traces"
        assert meta["settings"]["folds"] == {}
    assert found == MAPS


def test_the_steps_look_like_a_students(recorded):
    """The log is chosen and loaded, filtered as 03 filters it, and every map is `to_lcm_log` then `draw_map`."""
    _, _, nodes = recorded
    names = [node.operation.name for node in nodes.values()]
    assert names[:2] == ["choose_log", "load_log"]
    assert names.count("choose_log") == 2 and names.count("draw_map") == 8
    for i, name in enumerate(names):
        if name == "draw_map":
            assert names[i - 1] == "to_lcm_log"
    filters = [nodes[s].params["filters"] for s in _steps(nodes, "filter_log")]
    assert all(isinstance(text, str) for text in filters)  # JSON text, as 03 records it
    assert [ak._filters_from(t)[0]["value"] for t in filters[:4]] == [
        ["c3"], ["c3", "c1"], ["c3", "c1", "c4"], ["c3", "c1", "c4", "c2"],
    ]


def test_every_annotation_is_tagged_and_plain(recorded):
    _, _, nodes = recorded
    notes = _annotations(nodes)
    assert len(notes) == 29  # 8 intents and 21 findings
    for _, note in notes:
        tags = [t.name for t in note.tags]  # the panel keeps a note's tags sorted, so their order is not checked
        assert len(set(tags) & KINDS) == 1, tags
        assert len(set(tags) - KINDS) == 1 and set(tags) - KINDS <= TOPICS, tags
        assert "—" not in note.note, note.note
        assert note.note == note.note.strip() and note.note


def test_every_pin_names_a_part_of_the_map_of_its_step(recorded):
    """A trace, node or link an annotation points at is in the map that its step drew."""
    _, panel, nodes = recorded
    traces_pinned = 0
    for state, note in _annotations(nodes):
        for ref in note.artifacts:
            assert ref.artifact_id == state
            if ref.granularity not in ("trace", "node", "link"):
                assert ref.granularity == "chart_selection" and not ref.detail
                continue
            assert ref.artifact_name == "process_map" and nodes[state].operation.name == "draw_map"
            figure = panel.snapshot(state).get("map_figure")
            sankey = figure.data[0]
            labels = list(sankey.node.label)
            if ref.granularity == "trace":
                traces_pinned += 1
                assert ref.detail in [t["name"] for t in sankey.meta["lcm"]["traces"]], ref.detail
            elif ref.granularity == "node":
                assert ref.detail in labels, ref.detail
            else:
                links = [f"{labels[a]} -> {labels[b]} ({t})" for a, b, t in zip(sankey.link.source, sankey.link.target, sankey.link.label)]
                assert ref.detail in links, ref.detail
    assert traces_pinned >= 12


def test_a_walk_through_every_step_reads_a_consistent_log_filter_and_map(recorded):
    """What the reviewer notebook reads at each step: the chosen log, the filter recorded at or before that step (none from a
    log chosen after it), and the map. The map's cases are the cases of the filtered log."""
    from provenance_widget.snapshot import INITIAL_STATE

    adapter, panel, nodes = recorded
    assert ak.recorded_filter_at(adapter, INITIAL_STATE) == []
    assert panel.snapshot(INITIAL_STATE).status("log_name") == "not_computed"
    logs = {name: ak.normalise_log(ak.read_log(ROOT / "notebooks" / name)) for name in (TOY, SEPSIS)}
    chosen = None
    for state, node in nodes.items():
        snap = panel.snapshot(state)
        name = snap.get("log_name")
        if node.operation.name == "choose_log":
            chosen = node.params["name"]
        assert name == chosen
        filters = ak.recorded_filter_at(adapter, state)
        if name == SEPSIS:
            assert filters == []
        kept = ak.filter_log(logs[name], filters)
        if node.operation.name == "draw_map":
            assert snap.get("map_meta")["cases"] == kept[ak.CASE_ID].nunique()
            arguments = ak.params_at(adapter, state, "to_lcm_log")
            assert arguments.get("activity_column", ak.ACTIVITY) == ("folded_activity" if name == SEPSIS else ak.ACTIVITY)
        for _, note in [(s, a) for s, a in _annotations(nodes) if s == state]:
            assert note.note


def test_the_filter_of_a_step_is_the_last_one_before_it(recorded):
    adapter, _, nodes = recorded
    maps = _steps(nodes, "draw_map")
    cases = [
        sorted(v for c in ak.recorded_filter_at(adapter, s) for v in c["value"]) for s in maps[:4]
    ]
    assert cases == [["c3"], ["c1", "c3"], ["c1", "c3", "c4"], ["c1", "c2", "c3", "c4"]]


def test_the_knockout_finding_points_at_intensive_care(recorded):
    """Slide 38 boxes the thin links from several stages into Admission IC (the links into Release are the mainstream). One
    annotation has one anchor, so the finding points at the node those links lead into and names them in its text."""
    _, _, nodes = recorded
    knockout = [a for _, a in _annotations(nodes) if "knockout" in [t.name for t in a.tags]]
    assert len(knockout) == 1
    (ref,) = knockout[0].artifacts
    assert (ref.granularity, ref.detail) == ("node", "Admission IC")
    assert all(f"from {stage}" in knockout[0].note for stage in ("ER Sepsis Triage", "Admission NC", "ER Triage", "ER Registration"))


def test_every_annotation_has_one_anchor(recorded):
    """In the panel an annotation has exactly one target (Anchor and a click replace the previous one): the tutorial shows only what
    a student can do."""
    _, _, nodes = recorded
    for _, note in _annotations(nodes):
        assert len(note.artifacts) == 1, note.note
