# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo>=0.25.2",
#     "pmprov[duckdb,parquet,graph]>=0.10.0",
#     "marimo-pmprov[pdf]>=0.17.0",
#     "pandas>=3.1.0",
#     "anywidget",
#     "linear-continuous-process-mapper>=0.2.0",
#     "plotly>=7.1.0",
# ]
#
# [tool.marimo.opengraph]
# title = "04 Tutorial - Process Map"
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="04 Tutorial - Process Map")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Map explorer

    This page replays a recorded analysis: the arrows of the side panel move through it step by step. Nothing is saved here. If marimo shows a message that something failed, or the page stops responding, reload the page.
    """)
    return


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import shutil as _shutil
    import sys as _sys
    import tempfile as _tempfile
    import urllib.request as _request
    from pathlib import Path

    def _folder_of_this_notebook():
        try:
            folder = Path(str(mo.notebook_location()))
            if folder.is_dir():
                return folder
        except Exception:
            pass
        return Path.cwd()

    HERE = _folder_of_this_notebook()

    # The provenance panel's library (marimo-pmprov, the module `provenance_widget`): the copy that comes with the notebooks
    # (vendor/) is found before the installed one, so a start that brings the notebooks up to date brings it up to date too.
    _vendor = HERE / "vendor"
    if _vendor.is_dir() and str(_vendor) not in _sys.path:
        _sys.path.insert(0, str(_vendor))
    from provenance_widget.pmprov_adapter import PmprovAdapter
    from provenance_widget.widget import ProvenancePanel
    from provenance_widget.display import show_chart, show_table
    RAW_URL = "https://raw.githubusercontent.com/alvarobernal2412/bpm/main/"

    def project_file(relative, refresh=False):
        """A file of this project: next to the notebook in a local checkout, otherwise downloaded from the repository (molab
        delivers only the notebook file). The log is downloaded once, the small files each time, so they are current."""
        local = HERE / relative
        if local.exists():
            return local
        cached = Path(_tempfile.gettempdir()) / "bpm-project-files" / relative
        if refresh or not cached.exists():
            cached.parent.mkdir(parents=True, exist_ok=True)
            part = cached.with_name(cached.name + ".part")
            with _request.urlopen(RAW_URL + relative, timeout=600) as response, open(part, "wb") as out:
                _shutil.copyfileobj(response, out)
            part.replace(cached)
        return cached

    _kit_file = project_file("bpm_kit.py", refresh=True)
    if str(_kit_file.parent) not in _sys.path:
        _sys.path.insert(0, str(_kit_file.parent))
    import bpm_kit as kit

    kit.use_project_files(project_file)

    # the helper modules (the `lib/` folder of the repository), found next to the notebook or downloaded
    _lib = [project_file(f"lib/{name}.py", refresh=True) for name in (
        "temporal_characteristics_util", "data_quality_util", "xes_reader", "initial_analysis_kit")]
    if str(_lib[0].parent) not in _sys.path:
        _sys.path.insert(0, str(_lib[0].parent))
    import initial_analysis_kit as ak

    return HERE, PmprovAdapter, ProvenancePanel, ak, kit, mo, project_file, show_chart, show_table


@app.cell(hide_code=True)
def _(HERE, ak, mo):
    # The version of the notebooks and the button that stops the app, on every page, before anything else
    stop_button = mo.ui.run_button(label="Stop the app")
    ak.app_bar(mo, HERE, stop_button)
    return (stop_button,)


@app.cell(hide_code=True)
def _(ak, mo, stop_button):
    # made here, not inside the helper: marimo answers the click of a button only when it is a variable of the notebook
    confirm_stop = mo.ui.button(label="Yes, stop the app", kind="danger", on_click=lambda _: ak.stop_app())
    ak.stop_confirmation(mo, confirm_stop) if stop_button.value else None
    return (confirm_stop,)


@app.cell(hide_code=True)
def _(kit, mo):
    # The recorded analysis ships with the notebooks (histories/process-map-tutorial.zip, made by build/build_tutorial_history.py).
    # It is unpacked into a temporary folder and read from there: there is no key and no server, and nothing is written back.
    try:
        _folder, _ = kit.fetch_recorded(kit.PROCESS_MAP_TUTORIAL_ZIP, None, None)
        rt = kit.open_recorded(_folder, kit.PROCESS_MAP_TUTORIAL_HISTORY)
        _problem = None if rt is not None else "it has no analysis of that name"
    except Exception as _error:
        rt, _problem = None, str(_error)
    mo.stop(
        rt is None,
        mo.callout(mo.md(f"The recorded tutorial could not be opened ({_problem}). Reload the page."), kind="danger"),
    )
    return (rt,)


@app.cell(hide_code=True)
def _(PmprovAdapter, ProvenancePanel, mo, rt):
    adapter = PmprovAdapter(rt)
    # read only: the player steps through the recorded analysis, its annotations cannot be changed
    panel = ProvenancePanel(source=adapter, mode="reviewer", tabs=["curated"])
    panel.refresh()  # build the tree now, so the first snapshot below already knows its step
    # A tutorial is read from the beginning: the player starts on the first recorded step (a reviewer's panel starts on the latest)
    _first = next(iter(adapter.get_tree().nodes), None)
    if _first is not None:
        panel.go_to(_first)
    # Moved by the player and by Jump to anchor. Binding the cursor also turns on `outputs_follow_cursor`: the page follows the
    # player, and the panel highlights the anchors of a step's annotations when the student lands on that step.
    get_cursor = panel.reactive_cursor(mo.state)
    return adapter, get_cursor, panel


@app.cell(hide_code=True)
def _(mo, panel):
    # mo.sidebar(...) has to be the last bare expression of its cell to render
    mo.sidebar(panel.sidebar())
    return


@app.cell(hide_code=True)
def _(adapter, get_cursor, kit, mo, panel):
    # Here record(...) runs nothing: it returns what a step produced at the step the side panel is on.
    snap = panel.snapshot(get_cursor() or adapter.latest_state_id())
    record, state_of = kit.reviewer_recorder(snap, mo)
    return record, snap, state_of


@app.cell(hide_code=True)
def _(kit, mo, record):
    # The log that was chosen at this step (a recorded step of its own). The picker only shows it: the choice is the recorded one.
    LOGS = {"DFG example": "data/dfg-example.xes", "Sepsis cases": "data/SepsisCases2020EventLog.xes"}
    log_name = record(["log_name"], kit.choose_log, None)
    log_picker = mo.ui.dropdown(
        options=LOGS,
        value={path: label for label, path in LOGS.items()}.get(log_name),
        label="Choose an event log",
        disabled=True,
    )
    log_picker
    return (log_name,)


@app.cell(hide_code=True)
def _(adapter, ak, kit, log_name, mo, project_file, record, snap):
    # The log as the step loaded it; read again from its file if the recording did not keep it. A log chosen at this step is
    # loaded by the next one: the log loaded before it is not shown under its name.
    mo.stop(ak.made_before_choice(adapter, snap.state_id, "load_log"), mo.md("_The chosen log is loaded in the next step._"))
    event_log = record(["event_log"], ak.load_log, None)
    if isinstance(event_log, kit.NotStored):
        event_log = ak.load_log(project_file(log_name))
    mo.md(f"**{len(event_log):,}** events of **{event_log[ak.CASE_ID].nunique():,}** cases loaded.")
    return (event_log,)


@app.cell(hide_code=True)
def _(adapter, ak, event_log, snap, state_of):
    # The filter recorded at or before this step (none from a log chosen after it), and the log it keeps
    log_filters = ak.recorded_filter_at(adapter, snap.state_id)
    map_log = ak.filter_log(event_log, log_filters)
    _produced = getattr(snap, "produced_here", lambda _: False)
    log_state = state_of("filtered_log") if log_filters or _produced("filtered_log") else state_of("event_log")
    return log_state, log_filters, map_log


@app.cell(hide_code=True)
def _(log_state, map_log, mo, show_table):
    # One table in its own cell: the log as the recorded filter leaves it (a table cannot be opened with column filters set, and
    # nothing is edited in a replay). The filter is named above the map, as in the assignment notebook.
    show_table(mo.ui.table(map_log, page_size=5, selection=None), artifact_id=log_state, artifact_name="event_log")
    return


@app.cell(hide_code=True)
def _(kit, record):
    # the arguments are ignored here: record() returns what the recorded step drew
    map_figure, map_meta = record(
        ["map_figure", "map_meta"], kit.draw_map, None, None, None, None, None, None, None, name="draw_map"
    )
    return map_figure, map_meta


@app.cell(hide_code=True)
def _(adapter, ak, kit, log_name, mo, project_file, record, snap):
    # A log chosen after the last map has no map yet: the map of the other log is not shown with it
    mo.stop(
        ak.made_before_choice(adapter, snap.state_id, "draw_map"),
        mo.md("_No map of this log yet at this step. Step forward to draw it._"),
    )
    # The step that drew the map shown now, and the filter it was drawn from. A step can record a new filter before its map is drawn:
    # the map shown then is still the previous one, so its line names the filter of that map, not the one of the table.
    drawn_at = ak.step_state_id(adapter, snap.state_id, "draw_map")
    drawn_filters = ak.recorded_filter_at(adapter, drawn_at) if drawn_at else []
    _log = record(["event_log"], ak.load_log, None)  # no log was chosen after the shown map: it is the log of this step
    if isinstance(_log, kit.NotStored):
        _log = ak.load_log(project_file(log_name))
    drawn_log = ak.filter_log(_log, drawn_filters)
    drawn_total = _log[ak.CASE_ID].nunique()
    return drawn_at, drawn_filters, drawn_log, drawn_total


@app.cell(hide_code=True)
def _(adapter, ak, drawn_at, drawn_filters, drawn_log, drawn_total, kit, map_figure, map_meta, mo, show_chart, state_of):
    # the settings of the shown map: those of the step that drew it
    _column = (ak.params_at(adapter, drawn_at, "to_lcm_log") or {}).get("activity_column", ak.ACTIVITY)
    _filter = mo.md("")
    if drawn_filters:
        _filter = mo.md(
            f"**Filter:** {ak.filter_words(drawn_filters)} · {drawn_log[ak.CASE_ID].nunique():,} of "
            f"{drawn_total:,} cases are kept ({len(drawn_log):,} events)."
        )
    mo.vstack([
        mo.md(kit.describe_settings(map_meta["settings"]) if isinstance(map_meta, dict) else ""),
        mo.md(f"**Activity column:** `{_column}`" if _column != ak.ACTIVITY else ""),
        _filter,
        mo.md(kit.describe_map(map_meta)),
        mo.callout(
            mo.md(f"No event of these has a value for the attribute that makes up a path, so not drawn: {', '.join(f'`{a}`' for a in map_meta['left_out'])}."),
            kind="neutral",
        ) if isinstance(map_meta, dict) and map_meta.get("left_out") else mo.md(""),
        show_chart(mo.as_html(map_figure), artifact_id=state_of("map_figure"), artifact_name="process_map"),
    ])
    return


if __name__ == "__main__":
    app.run()
