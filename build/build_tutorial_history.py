"""Record the process map tutorial that `notebooks/04_tutorial-process-map.py` replays.

    python build/build_tutorial_history.py      # writes notebooks/histories/process-map-tutorial.zip

The analysis is made with the steps of the process map notebook `03` (`ak.record_filter`, `ak.to_lcm_log` with
`ak.lcm_log_arguments`, `kit.draw_map`, all through `ak.analyst_recorder`), and its annotations are written with the panel's
adapter, so it replays exactly like a student's work. It follows slides 34 to 39 of the lecture on behavior: the DFG example log
{A, AKLZ, AKLZ, ALKZ} is filtered case by case and drawn in the three abstractions, then the admin subprocess of the Sepsis log is
drawn as a DFG and with the set abstraction. The numbers in the annotations are computed from the logs here, so they always match
the maps.

Every annotation is tagged `intent` (what a map is for, on the whole map) or `finding` (what it shows), and one topic. A finding
points at the trace, node or link it is about, so the panel highlights it when a student steps to it.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"
# as the notebooks do: the library that comes with them (vendor/) before the installed one
for folder in (NOTEBOOKS / "lib", NOTEBOOKS, NOTEBOOKS / "vendor"):
    sys.path.insert(0, str(folder))

import bpm_kit as kit  # noqa: E402
import initial_analysis_kit as ak  # noqa: E402

warnings.filterwarnings("ignore", message=r"init_marimo\(\) was called but patch_marimo_ast_compile")
# pmprov records who made each step and note by the name of this computer's user; the tutorial is the course's
os.environ["LOGNAME"] = "course"

TOY = "data/dfg-example.xes"
SEPSIS = "data/SepsisCases2020EventLog.xes"
SEPSIS_COLUMN = "folded_activity"
ADMIN = ["Admission IC", "Admission NC", "ER Registration", "ER Sepsis Triage", "ER Triage", "Release"]
ER = ["ER Registration", "ER Triage", "ER Sepsis Triage"]
HEIGHT = 620
ROOM = (100, 140, 110)  # as in 03: the rings of the loops reach above, below and left of the nodes


def load_log(name: str):
    """The log at its place in the notebooks folder. The step records the name, not a folder of this computer (as `03` does)."""
    return ak.load_log(NOTEBOOKS / name)


class Session:
    """One recorded analysis: steps through `record`, annotations through the panel adapter."""

    def __init__(self, folder: Path, history_name: str):
        from provenance_widget.pmprov_adapter import PmprovAdapter
        from tracker import init_marimo

        if folder.exists():
            shutil.rmtree(folder)
        (folder / "artifacts").mkdir(parents=True)
        self.folder = folder
        self.rt = init_marimo(
            history_name=history_name,
            branch_name="main",
            db_path=str(folder / "provenance.db"),
            artifact_dir=str(folder / "artifacts"),
            fresh=True,
        )
        self.adapter = PmprovAdapter(self.rt)
        self.record, self.state_of = ak.analyst_recorder(self.rt, self.adapter)

    # --- the steps, as the notebook records them -------------------------------------------------------------------------------

    def choose(self, name: str):
        """Choose a log (a step of its own, so the reviewer's picker can show it) and load it."""
        self.record(["log_name"], kit.choose_log, name)
        self.log = self.record(["event_log"], load_log, name)
        self.map_log = self.log
        return self.log

    def filter(self, cases: list[str] | None):
        """The filter of `03`: a case filter (none for None) through `ak.record_filter`."""
        filters = ak.case_filter(cases) if cases else []
        self.map_log, _ = ak.record_filter(self.record, self.adapter, self.log, filters)
        return self.map_log

    def map(self, map_type: str, activities=None, activity_column: str = ak.ACTIVITY) -> dict:
        lcm_log = self.record(["lcm_log"], ak.to_lcm_log, self.map_log, *ak.lcm_log_arguments(ak.CASE_ID, activity_column))
        self.figure, self.meta = self.record(
            ["map_figure", "map_meta"], kit.draw_map,
            lcm_log, activities, map_type, True, True, {}, "application", HEIGHT, room=ROOM, layout="traces",
        )
        self.lcm_log = lcm_log
        self.traces = kit.traces_of(self.figure)  # the traces the figure stores (most frequent first)
        return self.meta

    # --- pins: the part of the current map that a finding is about --------------------------------------------------------------
    # Recorded the way the panel records a click on that part: a trace by its name, a node by its label, a link as
    # "source -> target (label)".

    def trace(self, name: str):
        assert name in [t["name"] for t in self.traces], name
        return "trace", name

    def trace_where(self, test):
        """The most frequent trace of the map whose sequence passes `test`."""
        found = [t for t in self.traces if test(t["sequence"])]
        assert found
        return found[0]

    def node(self, label: str):
        assert label in list(self.figure.data[0].node.label), label
        return "node", label

    def node_data(self, label: str) -> dict:
        sankey = self.figure.data[0]
        return sankey.node.customdata[list(sankey.node.label).index(label)]

    def links(self) -> list[dict]:
        sankey = self.figure.data[0]
        labels = list(sankey.node.label)
        return [
            {"source": labels[a], "target": labels[b], "label": text, "value": value, "detail": f"{labels[a]} -> {labels[b]} ({text})"}
            for a, b, text, value in zip(sankey.link.source, sankey.link.target, sankey.link.label, sankey.link.value)
        ]

    def link(self, item: dict):
        return "link", item["detail"]

    def link_from(self, source: str, target: str) -> dict:
        """The link of the map from `source` to `target` (not a self-loop)."""
        found = [l for l in self.links() if l["source"] == source and l["target"] == target]
        assert len(found) == 1, (source, target, found)
        return found[0]

    def leakiest_node(self, final: str):
        """The node where most traces end, among the nodes that are not the start and do not hold the `final` activity."""
        sankey = self.figure.data[0]
        candidates = [
            (data["leakage"], label)
            for label, data in zip(sankey.node.label, sankey.node.customdata)
            if label != "START" and final not in label.strip("{}").split(", ")
        ]
        return max(candidates)[1]

    # --- annotations -------------------------------------------------------------------------------------------------------------

    def intent(self, target: str, artifact_name: str, topic: str, text: str):
        """What a table or map is for: written right after it appears, on all of it."""
        self._note(target, artifact_name, text, ("intent", topic), None)

    def finding(self, target: str, artifact_name: str, topic: str, text: str, pin: tuple | None = None):
        """What a table or map shows. `pin` is (granularity, detail) of the one part it is about, from `trace`, `node` or `link`;
        without it the finding is about all of the table or map. One only: in the panel an annotation has one target."""
        self._note(target, artifact_name, text, ("finding", topic), pin)

    def _note(self, target, artifact_name, text, tags, pin):
        assert "—" not in text, text
        assert pin is None or (isinstance(pin, tuple) and len(pin) == 2 and all(isinstance(p, str) for p in pin)), pin
        state = self.state_of(target)
        picked = {"artifactId": state, "artifactName": artifact_name, "granularity": "chart_selection"}
        if pin is not None:
            picked["granularity"], picked["detail"] = pin
        self.adapter.persist_annotation(state, {"note": text, "tags": [{"name": t} for t in tags], "artifacts": [picked]})

    def finish(self, zip_path: Path) -> None:
        from provenance_widget.portable import zip_provenance

        self.rt.storage._executor.submit(lambda: None).result()  # let queued writes land
        old_storage_format(self.folder / "provenance.db")
        data, left_out = zip_provenance(self.folder)
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        zip_path.write_bytes(data)
        print(f"{zip_path.relative_to(ROOT)}: {len(data) / 1e6:.2f} MB; left out (too big to ship): {[name for name, _ in left_out]}")


def old_storage_format(db: Path) -> None:
    """Rewrite the provenance database in DuckDB's oldest storage format, which every DuckDB version opens. The artifacts are named
    by their file in `artifacts/` only, not by the folder of this computer (a reader points them at its own folder on opening)."""
    import duckdb
    from tracker.storage import _connect_lock

    target = db.with_name("portable.db")
    target.unlink(missing_ok=True)
    with _connect_lock:
        con = duckdb.connect()
        con.execute(f"ATTACH '{db.as_posix()}' AS source (READ_ONLY)")
        con.execute(f"ATTACH '{target.as_posix()}' AS target (STORAGE_VERSION 'v1.0.0')")
        con.execute("COPY FROM DATABASE source TO target")
        con.execute(r"UPDATE target.artifact_states SET content_ref = 'artifacts/' || regexp_extract(content_ref, '[^\\/]+$')")
        con.close()
    for leftover in (db, db.with_name(db.name + ".wal"), target.with_name(target.name + ".wal")):
        leftover.unlink(missing_ok=True)
    target.rename(db)


# --- facts from the logs ------------------------------------------------------------------------------------------------------


def sequences(lcm_log, activities=None):
    """Per case, its activities in time order (only `activities`, when given): what the map draws as its traces."""
    events = lcm_log if activities is None else lcm_log[lcm_log["concept:name"].isin(activities)]
    events = events.sort_values(["case:concept:name", "time:timestamp"], kind="stable")
    return events.groupby("case:concept:name")["concept:name"].apply(tuple)


def pct(part: int, whole: int) -> str:
    return f"{part / whole * 100:.1f}%"


def cases_word(n: int) -> str:
    return f"{n:,} case" + ("" if n == 1 else "s")


def times(n: int) -> str:
    return "once" if n == 1 else f"{n:,} times"


def follows(sequence, a, b) -> int:
    """How often `b` directly follows `a` in a sequence."""
    return sum(1 for x, y in zip(sequence, sequence[1:]) if (x, y) == (a, b))


# --- the tutorial ------------------------------------------------------------------------------------------------------------


def build(work: Path) -> None:
    s = Session(work / "process-map-tutorial", kit.PROCESS_MAP_TUTORIAL_HISTORY)
    MAP = "process_map"

    # 1. the DFG example log, the toy log of the slides
    toy = s.choose(TOY)
    case_traces = sequences(ak.to_lcm_log(toy, ak.CASE_ID))
    assert {c: "".join(t) for c, t in case_traces.items()} == {"c1": "AKLZ", "c2": "ALKZ", "c3": "A", "c4": "AKLZ"}
    s.intent(
        "event_log", "event_log", "sum-of-traces",
        f"Load the DFG example log, the toy event log of the slides, {{A, AKLZ, AKLZ, ALKZ}}: {len(case_traces)} cases, c1 = AKLZ, c2 = ALKZ, "
        f"c3 = A and c4 = AKLZ, {len(toy)} events. The next steps add the cases to a filter one at a time, in the order of the "
        "slides (c3, c1, c4, c2), and draw the sequence-based map after each one.",
    )

    # 2. one case, one trace
    s.filter(["c3"])
    meta = s.map("sequence_based")
    assert meta["cases"] == 1 and len(s.traces) == 1
    s.finding(
        "map_figure", MAP, "sum-of-traces",
        "The filter keeps one case, c3. Its trace is A, so the map is the map of one trace: one row from the start to the node A, "
        "where the case ends. The node is black because the case ends there.",
        s.trace("A"),
    )

    # 3. a second trace: the map is the sum of the maps of its traces
    s.filter(["c3", "c1"])
    meta = s.map("sequence_based")
    assert meta["cases"] == 2 and s.traces[0]["name"] == "A → K → L → Z"
    nodes_before = meta["total_nodes"]
    s.finding(
        "map_figure", MAP, "sum-of-traces",
        "With c1 the log has two traces, A (c3) and A → K → L → Z (c1). The map of the log is the sum of the maps of its traces "
        "(linearity): both traces share the link into A, 2 cases wide; then c3 ends at A and c1 goes on through K, L and Z. "
        "The highlighted trace is one band without a break: the map of a trace is the concatenation of the maps of its steps "
        "(continuity).",
        s.trace("A → K → L → Z"),
    )

    # 4. a case with a trace that is already there
    s.filter(["c3", "c1", "c4"])
    meta = s.map("sequence_based")
    main = s.traces[0]
    assert meta["cases"] == 3 and main["name"] == "A → K → L → Z" and main["cases"] == 2
    assert meta["total_nodes"] == nodes_before  # c4 adds no node to the map of c3 and c1
    s.finding(
        "map_figure", MAP, "sum-of-traces",
        f"c4 has the same trace as c1. The band of A → K → L → Z is now twice as wide ({cases_word(main['cases'])}) and the map has "
        f"no new node ({nodes_before} nodes, as before). A case whose trace is already in the map only makes the band of that trace "
        "wider.",
        s.trace("A → K → L → Z"),
    )

    # 5. the whole toy log, sequence-based (slide 34)
    s.filter(["c3", "c1", "c4", "c2"])
    meta = s.map("sequence_based")
    assert meta["cases"] == 4
    by_name = {t["name"]: t for t in s.traces}
    s.intent(
        "map_figure", MAP, "prefix-tree",
        "All four cases are in the filter now. Draw the whole DFG example log with the sequence-based abstraction (slide 34). This map is "
        "the prefix tree of the log: every node stands for one prefix, the exact sequence of activities a case has done so far.",
    )
    s.finding(
        "map_figure", MAP, "prefix-tree",
        f"The trace A → K → L → Z has {cases_word(by_name['A → K → L → Z']['cases'])}, c1 and c4: A, then K, L and Z. It is the "
        "widest band, from the start to the end.",
        s.trace("A → K → L → Z"),
    )
    s.finding(
        "map_figure", MAP, "prefix-tree",
        f"The grey node after K on the top band represents the prefix AK: the cases that did A and then K "
        f"({cases_word(s.node_data('A → K')['incoming_flow'])}, c1 and c4).",
        s.node("A → K"),
    )
    s.finding(
        "map_figure", MAP, "prefix-tree",
        f"The trace A → L → K → Z has {cases_word(by_name['A → L → K → Z']['cases'])}, c2. It leaves the other long trace after A, "
        "with L instead of K.",
        s.trace("A → L → K → Z"),
    )
    s.finding(
        "map_figure", MAP, "prefix-tree",
        "The grey node after K on the lower band represents the prefix ALK. It is not the node of the prefix AKL, although both "
        "prefixes hold the same three activities: in the prefix tree every prefix has a node of its own.",
        s.node("A → L → K"),
    )
    leak_a = s.node_data("A")["leakage"]
    s.finding(
        "map_figure", MAP, "prefix-tree",
        f"The trace A has {cases_word(by_name['A']['cases'])}, c3. It ends at the node A, which is dark: {leak_a} of the "
        f"{s.node_data('A')['incoming_flow']} cases that reach A ends there. Traces that end at a node where the process is not "
        "finished are leakage.",
        s.trace("A"),
    )

    # 6. set-based (slide 35)
    meta = s.map("set_based")
    s.intent(
        "map_figure", MAP, "set-abstraction",
        "Draw the same log with the set-based abstraction (slide 35). A node now stands for the set of activities done so far, "
        "whatever their order.",
    )
    akl = s.node_data("{A, K, L}")
    assert akl["leakage"] == 0 and [l["target"] for l in s.links() if l["source"] == "{A, K, L}"] == ["{A, K, L, Z}"]
    for label in ("{A}", "{A, K}", "{A, L}"):
        s.node(label)  # the nodes the two texts below name
    s.finding(
        "map_figure", MAP, "set-abstraction",
        f"The trace A → K → L → Z ({cases_word(by_name['A → K → L → Z']['cases'])}) goes from {{A}} to {{A, K}} and then to "
        "{A, K, L}: the same node that the trace A → L → K → Z reaches through {A, L}.",
        s.trace("A → K → L → Z"),
    )
    s.finding(
        "map_figure", MAP, "set-abstraction",
        f"The trace A → L → K → Z ({cases_word(by_name['A → L → K → Z']['cases'])}) goes from {{A}} to {{A, L}} and then to "
        "{A, K, L}, the node that the trace A → K → L → Z reaches through {A, K}. After three steps both traces have done A, K and "
        f"L, in another order: the set abstraction merges the prefixes AKL and ALK into one node, so this map has "
        f"{meta['total_nodes']} nodes and loses the order.",
        s.trace("A → L → K → Z"),
    )
    s.finding(
        "map_figure", MAP, "set-abstraction",
        f"The node {{A, K, L}} represents all prefixes made of the activities A, K and L: AKL (c1 and c4) and ALK (c2). "
        f"{cases_word(akl['incoming_flow'])} reach it and all of them go on to Z.",
        s.node("{A, K, L}"),
    )

    # 7. last-activity-based, the DFG (slide 37)
    meta = s.map("last_activity_based")
    s.intent(
        "map_figure", MAP, "dfg",
        "Draw the same log with the last-activity-based abstraction, the directly-follows graph or DFG (slide 37). A node now "
        "stands for the last activity done so far.",
    )
    kl = sum(follows(t, "K", "L") for t in case_traces)
    lk = sum(follows(t, "L", "K") for t in case_traces)
    around = sum(1 for t in case_traces if "".join(t).find("KLK") >= 0 or "".join(t).find("LKL") >= 0)
    assert kl == by_name["A → K → L → Z"]["cases"] and lk == by_name["A → L → K → Z"]["cases"] and around == 0
    s.finding(
        "map_figure", MAP, "dfg",
        f"The trace A → K → L → Z ({cases_word(by_name['A → K → L → Z']['cases'])}) follows the link from K to L, so that link is "
        f"{cases_word(kl)} wide. It never goes from L back to K.",
        s.trace("A → K → L → Z"),
    )
    s.finding(
        "map_figure", MAP, "dfg",
        f"The trace A → L → K → Z ({cases_word(by_name['A → L → K → Z']['cases'])}) follows the K and L links the other way: from "
        f"L to K ({times(lk)}). It never goes from K back to L.",
        s.trace("A → L → K → Z"),
    )
    s.finding(
        "map_figure", MAP, "dfg",
        "The link from L to K closes a cycle between K and L in this map, but no case follows the cycle: no trace does K, L and "
        "then K again. In a DFG a cycle can come from two traces that do the same activities in another order, and not only from "
        "a repetition; here no case repeats K or L.",
        s.link(s.link_from("L", "K")),
    )
    node_l = s.node_data("L")
    s.finding(
        "map_figure", MAP, "dfg",
        f"The node L represents all prefixes that end with L: AL (c2), AKL (c1) and AKL (c4). {cases_word(node_l['incoming_flow'])} "
        "reach it, coming from A and from K.",
        s.node("L"),
    )

    # 8. the Sepsis log, its admin subprocess
    sepsis = s.choose(SEPSIS)
    s.filter(None)  # no filter: after the filters of the DFG example log this is recorded as a filter step with none, as 03 records it
    traces = sequences(ak.to_lcm_log(sepsis, ak.CASE_ID, SEPSIS_COLUMN), ADMIN)
    n = int(sepsis[ak.CASE_ID].nunique())

    # 9. DFG (slide 38)
    meta = s.map("last_activity_based", ADMIN, SEPSIS_COLUMN)
    assert meta["cases"] == n and meta["empty_cases"] == 0
    s.intent(
        "map_figure", MAP, "dfg",
        f"Switch to the Sepsis log and draw its admin subprocess: the activity column {SEPSIS_COLUMN} with the activities "
        f"{', '.join(ADMIN)}, empty traces shown, in the last-activity-based abstraction, the DFG (slide 38). The {n:,} cases are "
        "patients who come to the emergency room (ER), may be admitted to normal care (NC) or intensive care (IC), and most are released.",
    )
    main = s.traces[0]
    assert traces.value_counts().iloc[0] == main["cases"] and tuple(main["sequence"]) == traces.value_counts().index[0]
    s.finding(
        "map_figure", MAP, "mainstream",
        f"Mainstream behavior: the most frequent trace is {main['name']}, {cases_word(main['cases'])} ({pct(main['cases'], n)}). "
        "It is the sequence of thick links from the start, highlighted here.",
        s.trace(main["name"]),
    )
    # slide 38 boxes the thin links that run from several stages into the small node at the top right: Admission IC
    IC = "Admission IC"
    into_ic = sorted(
        (l for l in s.links() if l["label"].startswith(IC + " (") and l["source"] != IC), key=lambda l: -l["value"]
    )
    assert len(into_ic) >= 3
    for l in into_ic:
        assert l["value"] == sum(follows(t, l["source"], IC) for t in traces), l
    intensive = int(traces.apply(lambda t: IC in t).sum())
    released = int(traces.apply(lambda t: "Release" in t).sum())
    s.finding(
        "map_figure", MAP, "knockout",
        f"Knockout structure: at several stages cases are taken out of the main path into intensive care, the node {IC}. "
        f"The links into it come from {len(into_ic)} earlier stages: "
        + ", ".join(f"{times(l['value'])} from {l['source']}" for l in into_ic)
        + f". {cases_word(intensive)} ({pct(intensive, n)}) are admitted to intensive care at least once; they leave the "
        "mainstream path at the stage where this happens.",
        s.node(IC),
    )
    leaky = s.leakiest_node("Release")
    ending = int(traces.apply(lambda t: t[-1] == leaky).sum())
    assert ending == s.node_data(leaky)["leakage"]
    s.finding(
        "map_figure", MAP, "leakage",
        f"Leakage: {cases_word(ending)} ({pct(ending, n)}) end at the node {leaky}, the node where most cases end without reaching "
        f"Release, the expected end state. In total {n - released:,} cases never reach Release.",
        s.node(leaky),
    )
    loop = max((l for l in s.links() if l["source"] == l["target"]), key=lambda l: l["value"])
    activity = loop["source"]
    pairs = {(l["source"], l["target"]) for l in s.links()}
    assert {("Admission NC", IC), (IC, "Admission NC")} <= pairs  # the cycle the text names
    repeated = int(traces.apply(lambda t: follows(t, activity, activity) > 0).sum())
    assert loop["value"] == sum(follows(t, activity, activity) for t in traces)
    s.finding(
        "map_figure", MAP, "rework",
        f"Probably rework: the self-loop on {activity} is the heaviest loop of the map. {activity} directly follows {activity} "
        f"{times(loop['value'])}, in {cases_word(repeated)}. The DFG also draws cycles between nodes, for example between "
        "Admission NC and Admission IC, and a cycle can come from another order as well as from a repetition. The DFG alone "
        "does not prove rework: the set abstraction does (next map).",
        s.link(loop),
    )

    # 10. set-based (slide 39)
    meta = s.map("set_based", ADMIN, SEPSIS_COLUMN)
    s.intent(
        "map_figure", MAP, "set-abstraction",
        "Draw the same activities with the set-based abstraction (slide 39) and compare it with the DFG.",
    )
    assert s.traces[0]["name"] == main["name"]
    s.finding(
        "map_figure", MAP, "mainstream",
        f"Mainstream behavior: the same trace, {main['name']}, {cases_word(main['cases'])}. In this map it is a straight band "
        "from the start: every step adds an activity to the set.",
        s.trace(main["name"]),
    )
    loop = max((l for l in s.links() if l["source"] == l["target"]), key=lambda l: l["value"])
    activity = loop["label"].rsplit(" (", 1)[0]
    again = int(traces.apply(lambda t: t.count(activity) >= 2).sum())
    s.finding(
        "map_figure", MAP, "rework",
        f"Definitely rework: a self-loop on a set node means that a case does an activity that is already in its set, so the "
        f"set does not change. The heaviest one is {activity} on the node {loop['source']}: {times(loop['value'])}. "
        f"{cases_word(again)} ({pct(again, n)}) have {activity} two or more times.",
        s.link(loop),
    )
    main_order = tuple(ER)
    other = s.trace_where(lambda q: len(q) >= 3 and set(q[:3]) == set(ER) and tuple(q[:3]) != main_order)
    other_order = int(traces.apply(lambda t: len(t) >= 3 and set(t[:3]) == set(ER) and t[:3] != main_order).sum())
    s.finding(
        "map_figure", MAP, "ordering",
        f"Exceptional behavior: the thin links below the main path are traces that do the three ER activities in another order. "
        f"The most frequent one is {other['name']}, {cases_word(other['cases'])}; {cases_word(other_order)} start with another "
        f"order of {', '.join(ER)}. In the set abstraction they meet the main path again once the set is the same.",
        s.trace(other["name"]),
    )
    leaky = s.leakiest_node("Release")
    ending = s.node_data(leaky)["leakage"]
    s.finding(
        "map_figure", MAP, "leakage",
        f"Leakage: {cases_word(ending)} ({pct(ending, n)}) end at the node {leaky}: they have done these activities and do not "
        "reach Release, the expected end state.",
        s.node(leaky),
    )

    s.finish(NOTEBOOKS / kit.PROCESS_MAP_TUTORIAL_ZIP)


if __name__ == "__main__":
    work = Path(tempfile.mkdtemp(prefix="hs-tutorial-build-"))
    try:
        build(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
