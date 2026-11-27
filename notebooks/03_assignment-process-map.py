# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo>=0.25.2",
#     "pmprov[duckdb,parquet,graph]>=0.10.0",
#     "marimo-pmprov[pdf]>=0.17.0",
#     "pandas>=3.1.0",
#     "pyarrow>=15",
#     "altair>=5.5",
#     "vegafusion>=2.0",
#     "pytz",
#     "linear-continuous-process-mapper>=0.2.0",
#     "plotly>=7.1.0",
#     "kaleido>=1.0.0",
#     "networkx>=3.7",
# ]
#
# [tool.marimo.opengraph]
# title = "03 Assignment - Process Map"
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="03 Assignment - Process Map")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Map explorer

    Your work is saved automatically. You can close this page and continue later. If marimo shows a message that something failed, or the page stops responding, reload the page: your work comes back as you left it.
    """)
    return


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import pandas as pd
    import os as _os
    import shutil as _shutil
    import sys as _sys
    import tempfile as _tempfile
    import urllib.request as _request
    import warnings as _warnings
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
    from tracker import init_marimo
    from provenance_widget.pmprov_adapter import PmprovAdapter
    from provenance_widget.widget import ProvenancePanel
    from provenance_widget.display import show_chart, show_table
    from provenance_widget.portable import relocate_artifacts
    from provenance_widget.repeats import describe_run
    from provenance_widget.sync import Sync
    try:  # where the nodes of the map were dragged to (marimo-pmprov 0.16); without it the map is shown as it is drawn
        from provenance_widget import arrangement
    except ImportError:
        arrangement = None
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

    # the helper modules of the analysis (the `lib/` folder of the repository), found next to the notebook or downloaded
    _lib = [project_file(f"lib/{name}.py", refresh=True) for name in (
        "temporal_characteristics_util", "data_quality_util", "display_util", "initial_analysis_kit")]
    if str(_lib[0].parent) not in _sys.path:
        _sys.path.insert(0, str(_lib[0].parent))
    import altair as alt
    import display_util as du
    import initial_analysis_kit as ak
    import temporal_characteristics_util as tcu

    alt.data_transformers.enable("vegafusion")

    # The course server that keeps each student's work. Set PMPROV_SYNC_URL to another address, or to an empty value to work
    # without a server (the work then stays in ./provenance next to the notebook).
    SYNC_URL = ak.course_server(_os.environ.get("PMPROV_SYNC_URL", "https://provenance.alvispace.com"))
    # (a student who said no to sharing has no server here, however the notebook was started: see ak.course_server)

    # pmprov warns that its cell rewriting is not active; the steps are recorded explicitly with record() below
    _warnings.filterwarnings("ignore", message=r"init_marimo\(\) was called but patch_marimo_ast_compile")
    return (
        HERE,
        Path,
        PmprovAdapter,
        ProvenancePanel,
        SYNC_URL,
        Sync,
        ak,
        arrangement,
        describe_run,
        du,
        init_marimo,
        kit,
        mo,
        pd,
        project_file,
        relocate_artifacts,
        show_chart,
        show_table,
        tcu,
    )


@app.cell(hide_code=True)
def _(HERE, ak, mo):
    # The version of the notebooks and the button that stops the app, on every page, before anything else (also before a key is entered)
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
def _(SYNC_URL, kit, mo):
    key_box = mo.ui.anywidget(kit.KeyBox()) if SYNC_URL else None
    mo.vstack([mo.md("### Your key"), key_box]) if key_box is not None else mo.md("")
    return (key_box,)


@app.cell(hide_code=True)
def _(HERE, Path, SYNC_URL, Sync, ak, key_box, kit, mo):
    # With a server, nothing starts until there is a key; then the student's earlier work is brought back before anything opens
    # the provenance database.
    sync = None
    if SYNC_URL:
        _key = (key_box.value.get("key") or "").strip()
        mo.stop(not _key, mo.callout(mo.md("Enter your key above to start."), kind="info"))
        PROVENANCE_DIR = ak.session_folder(_key, ak.MAP_EXPLORER_NOTEBOOK)
        sync = Sync(ak.sync_url(SYNC_URL, ak.MAP_EXPLORER_NOTEBOOK), _key, PROVENANCE_DIR)
        sync.restore()
        mo.stop(sync.status.state == "unauthorized", mo.callout(mo.md(sync.status.message), kind="danger"))
    else:
        PROVENANCE_DIR = Path(kit.os.environ.get("PMPROV_DIR") or HERE / "provenance")
    (PROVENANCE_DIR / "artifacts").mkdir(parents=True, exist_ok=True)
    # which notebook this is, and a hash of its file: saved with the work, so the course server knows what version made it
    _info_file = ak.write_notebook_info(PROVENANCE_DIR, ak.MAP_EXPLORER_NOTEBOOK, globals().get("__file__"))  # kept, so it is not shown
    return PROVENANCE_DIR, sync


@app.cell(hide_code=True)
def _(PROVENANCE_DIR, ak, init_marimo, kit, relocate_artifacts):
    # a history that was downloaded from another machine points at that machine's folders
    relocate_artifacts(PROVENANCE_DIR / "provenance.db", PROVENANCE_DIR / "artifacts")
    rt = init_marimo(
        history_name=ak.MAP_EXPLORER_HISTORY_NAME,
        branch_name="main",
        db_path=str(PROVENANCE_DIR / "provenance.db"),
        artifact_dir=str(PROVENANCE_DIR / "artifacts"),
        fresh=False,  # continue the stored history of this name after a restart
    )
    return (rt,)


@app.cell(hide_code=True)
def _(PmprovAdapter, ProvenancePanel, rt):
    adapter = PmprovAdapter(rt)
    # the student can annotate, edit and export; there is no other mode in this notebook
    panel = ProvenancePanel(
        source=adapter,
        mode="analyst",
        tabs=["curated"],
        # marimo's Visualize on every table, and the charts built there recorded and brought back on their own tables. The panel
        # finds a table's cell by the artifact_name written in it, so every table is shown by a cell of its own (see the README).
        capture_charts=True,
        empty_hint=(
            "No annotations yet. Press Anchor, click the map (or a node or link of it) the annotation is about, write it with tags "
            "(for example intent or finding) and press Add."
        ),
    )
    return adapter, panel


@app.cell(hide_code=True)
def _(mo, panel):
    # mo.sidebar(...) has to be the last bare expression of its cell to render
    mo.sidebar(panel.sidebar())
    return


@app.cell(hide_code=True)
def _(arrangement, mo):
    # shows nothing: tells the notebook where the nodes of the map were dragged to (provenance_widget.arrangement)
    map_arrangement = mo.ui.anywidget(arrangement.NodeArrangement()) if arrangement else None
    map_arrangement
    return (map_arrangement,)


@app.cell(hide_code=True)
def _(mo, rt, sync):
    # saving starts once the history is open, and goes on a few seconds after every change
    if sync is not None:
        sync.settle = lambda: rt.storage._executor.submit(lambda: None).result()
        sync.start()
    save_tick = mo.ui.refresh(default_interval="5s", label="")
    return (save_tick,)


@app.cell(hide_code=True)
def _(mo, save_tick, sync):
    save_tick  # runs again every few seconds
    _parts = []
    if sync is not None:
        _kind = {"saved": "success", "idle": "neutral", "pending": "info", "conflict": "danger"}.get(sync.status.state, "warn")
        _parts.append(mo.callout(mo.md(sync.status.message), kind=_kind))
    mo.vstack(_parts + [save_tick.style(display="none")])  # the timer has to be on the page to tick, but it is not a control
    return


@app.cell(hide_code=True)
def _(adapter, ak, rt):
    # Every step of the analysis goes through record(...): it runs the step and stores it, so that an annotation can be attached to the
    # table or map that the step produced, and the analysis can be replayed step by step.
    record, state_of = ak.analyst_recorder(rt, adapter)
    return record, state_of


@app.cell(hide_code=True)
def _(HERE, ak, mo, project_file, record):
    # The log is not public and not part of the package: the launcher downloads it with the course code. Without it, say so.
    mo.stop(ak.log_is_missing(HERE), mo.callout(mo.md(ak.MISSING_LOG), kind="warn"))
    # Load the event log; the step records the name of the file, not a folder of somebody's computer
    def load_event_log(name):
        return ak.load_event_log(project_file(name))

    event_log = record(["event_log"], load_event_log, ak.DHANA)
    mo.md(f"**{len(event_log):,}** events of **{event_log[ak.CASE_ID].nunique():,}** cases loaded.")
    return (event_log,)


@app.cell(hide_code=True)
def _(ak, du, event_log, mo, show_table, state_of):
    # This notebook does not share data with the initial analysis: it reads the log again. The table is shown (not folded away): it
    # is where the filter of the map is set. Its column filters are the filter
    # of the map: Refresh visualization takes them (`ak.table_filters`). A filter in the browser runs no cell, so the table is watched
    # (`ak.watch_filters`): until it is filtered in this session, Refresh keeps the filter the map was last drawn with.
    event_table = ak.watch_filters(du.table(event_log, page_size=5))
    mo.vstack([
        mo.md("## Event log"),
        show_table(event_table, artifact_id=state_of("event_log"), artifact_name="event_log"),
        mo.md("Filter the table with the menu of a column; the map uses the filter when you press Refresh visualization."),
    ])
    return (event_table,)


@app.cell(hide_code=True)
def _(adapter, ak, event_log, kit, mo):
    # The controls are built from the whole log, not from what the filter keeps: a change of the filter does not make them again
    # (and lose what the analyst set). The map and the counts are drawn from the filtered log; an activity that the filter left out
    # is named under the map.
    # "Group events by": the attributes whose values can make up a path; the case id is the normal one
    explorer_notions = {("Case ID" if c == ak.CASE_ID else c): c for c in ak.path_attribute_options(event_log)}
    # "Activity column": the column whose values are the nodes of the map. It starts as the analyst left it.
    _recorded = ak.params_at(adapter, None, "to_lcm_log") or {}
    _options = ak.activity_column_options(event_log)
    _activity = _recorded.get("activity_column") if _recorded.get("activity_column") in _options else ak.ACTIVITY
    activity_column_dropdown = mo.ui.dropdown(
        options=_options,
        value=_activity,
        label="Activity column",
        allow_select_none=False,
    )
    # "Time frame": only the cases that lie completely inside it are drawn. The slider is a control of its own, so choosing another
    # activity column does not move it.
    map_time_frame = ak.time_frame(event_log, ak.CASE_ID, ak.TIMESTAMP)
    _stop = map_time_frame["stop"]
    _window = ak.time_frame_window(_recorded.get("window"), _stop)
    time_frame_slider = mo.ui.range_slider(
        start=0, stop=_stop, step=1, value=_window or [0, _stop], full_width=True, debounce=True,
        label=f"Time frame in {'days' if map_time_frame['unit'] == 'D' else 'hours'} after {map_time_frame['start']}",
    )
    # drawn: what the map shows (changed by Refresh). The explorer starts on the 5 most frequent activities (all 25 make a map of 342
    # nodes that takes ten seconds to draw and is slow to render in the browser) or as the analyst left it (including what each
    # path was). It does not depend on the activity column dropdown, so choosing another column changes nothing until Refresh is pressed.
    _column = _recorded.get("case_column")
    initial_settings = kit.normalise_settings(
        {
            **(kit.last_map_settings(adapter) or {"activities": sorted(event_log[_activity].value_counts().index[:5])}),
            "case_notion": _column if _column in explorer_notions.values() else ak.CASE_ID,
            "activity_column": _activity,
            "time_frame": _window,  # None is the whole log
            "filter": ak.last_filter(adapter),  # the filter of the map the analyst left ([] for none)
        }
    )
    get_drawn, set_drawn = mo.state(initial_settings)
    # The last filter that was recorded, so the same filter is not recorded again at every Refresh (`ak.record_filter`)
    filter_memo = {}
    # "Clear filter": draws the map from the whole log. Shown while a recorded filter is kept that the table does not show.
    clear_filter_button = mo.ui.button(label="Clear filter", on_click=lambda _: set_drawn(lambda d: {**d, "filter": []}))
    # The controls that do not depend on the activity column (see `kit.KEPT_CONTROLS`), as the analyst last set them. A plain dict, not
    # a state: it is filled by the cell below and read by the cell that builds the controls, which must not run again when it changes.
    # (it also keeps the selected activities and the fold rows, for as long as the activity column is the same one).
    kept_controls = {}
    # "Add fold" raises a counter; the cell that builds the controls reads it and makes the controls again with one more fold row.
    get_fold_adds, set_fold_adds = mo.state(0)
    add_fold_button = mo.ui.button(label="Add fold", on_click=lambda _: set_fold_adds(lambda n: n + 1))
    return activity_column_dropdown, add_fold_button, clear_filter_button, explorer_notions, filter_memo, get_drawn, get_fold_adds, initial_settings, kept_controls, map_time_frame, set_drawn, time_frame_slider


@app.cell(hide_code=True)
def _(activity_column_dropdown, event_log, explorer_notions, get_fold_adds, initial_settings, kept_controls, kit, mo):
    # Choosing another activity column builds the activity picker (and the folds) again for that column; the map is not drawn again
    # until Refresh is pressed. The other controls keep what the analyst set (`kept_controls`, empty the first time this runs).
    activity_column = activity_column_dropdown.value
    explorer_names = sorted(event_log[activity_column].dropna().unique())
    if activity_column == initial_settings["activity_column"]:
        draft_settings = initial_settings
    else:
        draft_settings = kit.normalise_settings(
            {
                "activities": sorted(event_log[activity_column].value_counts().index[:5]),
                "case_notion": initial_settings["case_notion"],
                "activity_column": activity_column,
                "time_frame": initial_settings["time_frame"],
            }
        )
    # The folds are optional: a row for each fold of the settings (a recorded history can have some), and one more for every click on
    # "Add fold". What was typed in the rows and the selected activities stay while the column stays.
    map_controls = kit.build_map_controls(mo, explorer_names, draft_settings, explorer_notions, kept_controls, activity_column, get_fold_adds())
    return activity_column, explorer_names, map_controls


@app.cell(hide_code=True)
def _(activity_column, kept_controls, kit, map_controls):
    # Runs whenever a control changes: remembers the controls that survive a change of the activity column, and the activities and
    # folds that survive adding a fold row. Shows nothing.
    kept_controls.update(kit.kept_controls_of(map_controls.value))
    kept_controls.update(kit.kept_column_controls_of(map_controls.value, activity_column))
    return


@app.cell(hide_code=True)
def _(activity_column, ak, event_table, explorer_names, get_drawn, kit, map_controls, map_time_frame, mo, set_drawn, time_frame_slider):
    # The filter is the table's, once the student has filtered the table in this session; until then the map keeps its filter (a
    # recorded one: the table cannot show it again after a reload).
    refresh_button = mo.ui.button(
        label="Refresh visualization", kind="success",
        on_click=lambda _: set_drawn({
            **kit.settings_from(map_controls.value, explorer_names), "activity_column": activity_column,
            "time_frame": ak.time_frame_window(time_frame_slider.value, map_time_frame["stop"]),
            "filter": ak.table_filters(event_table) if ak.table_was_filtered(event_table) else get_drawn().get("filter", []),
        }),
    )
    return (refresh_button,)


@app.cell(hide_code=True)
def _(adapter, ak, event_log, filter_memo, get_drawn, map_time_frame, record):
    # The log the map is drawn from: what the filter of the drawn settings keeps. A filter is a recorded step (`filter_log`), so that
    # an annotation written after it is about the filtered log, and a notebook that is opened again draws its map with it. No filter
    # is no step, so histories without a filter replay as they were.
    drawn_filter = get_drawn().get("filter") or []
    map_log, _ = ak.record_filter(record, adapter, event_log, drawn_filter, filter_memo)
    # Where the time frame counts from: the start of the whole log, whose slider it is, also when the log is filtered. None is the
    # log's own start, so a map of the whole log records its step as before.
    map_origin = ak.window_origin(map_time_frame) if map_log is not event_log else None
    return drawn_filter, map_log, map_origin


@app.cell(hide_code=True)
def _(ak, map_log, map_origin, map_time_frame, mo, time_frame_slider):
    # The time frame is a section of its own, before the settings of the map: it limits the log that every map is drawn from.
    # The count follows the slider at once (and counts what the filter keeps); the map changes only when Refresh is pressed.
    _cases, _events = ak.cases_in_time_frame(map_log, ak.time_frame_window(time_frame_slider.value, map_time_frame["stop"]), map_origin)
    mo.vstack([
        mo.md("## Time frame"),
        mo.md("Only the cases that lie completely in the time frame are drawn. A shorter time frame makes a smaller map."),
        time_frame_slider,
        mo.md(f"**{_cases:,}** cases and **{_events:,}** events lie completely in this time frame."),
    ])
    return


@app.cell(hide_code=True)
def _(activity_column, activity_column_dropdown, add_fold_button, ak, explorer_names, explorer_notions, get_drawn, kit, map_controls, map_time_frame, mo, refresh_button, time_frame_slider):
    _window = ak.time_frame_window(time_frame_slider.value, map_time_frame["stop"])
    # (the table's filter triggers nothing, so the status cannot see it: the line under the table says so)
    _current = {
        **kit.settings_from(map_controls.value, explorer_names), "activity_column": activity_column, "time_frame": _window,
        "filter": get_drawn().get("filter", []),
    }
    mo.vstack([
        mo.md("## Map settings"),
        kit.controls_layout(
            mo, map_controls, mo.md(""), refresh_button,
            kit.refresh_status(mo, _current, get_drawn()), show_case_notion=len(explorer_notions) > 1,
            activity_column=activity_column_dropdown, add_fold=add_fold_button,
        ),
    ])
    return


@app.cell(hide_code=True)
def _(ak, event_log, get_drawn, kit, map_log, map_origin, mo, panel, record):
    _settings = get_drawn()
    mo.stop(_settings is None, mo.md("*Choose the settings, then press Refresh visualization.*"))
    _problems = kit.fold_problems(_settings)
    mo.stop(bool(_problems), mo.callout(mo.md("  \n".join(_problems)), kind="danger"))
    mo.stop(_settings["activities"] == [], mo.callout(mo.md("Select at least one activity."), kind="warn"))
    path_column = _settings["case_notion"]  # "Group events by": the attribute whose values make up a path
    drawn_activity_column = _settings.get("activity_column", ak.ACTIVITY)  # a history from before this choice has none
    drawn_time_frame = _settings.get("time_frame")  # None is the whole log
    # the map is drawn from what the filter keeps: it must still have the columns that make up the paths and the nodes
    _problem = ak.filter_problem(event_log, map_log, needed=[path_column, drawn_activity_column])
    mo.stop(_problem is not None, mo.callout(mo.md(_problem or ""), kind="warn"))
    mo.stop(
        ak.cases_in_time_frame(map_log, drawn_time_frame, map_origin)[0] == 0,
        mo.callout(mo.md("No case lies completely within the time frame. Widen it and press Refresh visualization."), kind="warn"),
    )
    try:
        # every map you ask for is a recorded step: first the log with that attribute as the case, then the map of it
        lcm_log = record(
            ["lcm_log"], ak.to_lcm_log, map_log, *ak.lcm_log_arguments(path_column, drawn_activity_column, drawn_time_frame, map_origin)
        )
        map_figure, map_meta = record(
            ["map_figure", "map_meta"], kit.draw_map,
            lcm_log, _settings["activities"], _settings["map_type"], _settings["allow_loops"],
            _settings["show_empty"], _settings["folds"], "application", 900,  # the log's own case column is now the chosen attribute
            room=(100, 140, 110),  # the rings of the loops reach above, below and left of the nodes: with less room they are cut off
        )
        panel.refresh()  # so that the side panel knows the new step before the first annotation is written on it
    except ValueError as _error:
        _available = ", ".join(f"`{a}`" for a in sorted(lcm_log["concept:name"].unique()))
        _occur = f" The activities that occur when events are grouped by `{path_column}` are: {_available}." if _available else ""
        mo.stop(True, mo.callout(mo.md(f"{_error}{_occur}"), kind="danger"))
    return drawn_activity_column, drawn_time_frame, map_figure, map_meta, path_column


@app.cell(hide_code=True)
def _(adapter, arrangement, kit, map_arrangement, map_figure, panel, record, state_of):
    # Dragging a node happens in the browser only. Where the nodes were dragged to is recorded as a step of its own, so that an
    # annotation written after it shows the map as it was arranged, and a notebook that is opened again shows it as it was left.
    _drawn = state_of("map_figure")
    _positions = None
    if map_arrangement is not None:
        _positions = arrangement.reported(map_arrangement.value, _drawn) or kit.last_arrangement(adapter, _drawn)
    if _positions:
        shown_map = record(["arranged_map"], arrangement.arranged, map_figure, _positions, name="arrange_map")
        shown_map_state = state_of("arranged_map")
        panel.refresh()  # so that the side panel knows the new step before an annotation is written on it
    else:
        shown_map, shown_map_state = map_figure, _drawn
    return shown_map, shown_map_state


@app.cell(hide_code=True)
def _(ak, arrangement, clear_filter_button, drawn_activity_column, drawn_filter, drawn_time_frame, event_log, event_table, kit, map_log, map_meta, map_time_frame, mo, path_column, pd, show_chart, shown_map, shown_map_state, state_of):
    _chart = show_chart(mo.as_html(shown_map), artifact_id=shown_map_state, artifact_name="process_map")
    _filter = mo.md("")
    if drawn_filter:
        _filter = mo.md(
            f"**Filter:** {ak.filter_words(drawn_filter)} · {map_log[ak.CASE_ID].nunique():,} of "
            f"{event_log[ak.CASE_ID].nunique():,} cases are kept ({len(map_log):,} events)."
        )
        if not ak.table_was_filtered(event_table):  # a recorded filter, kept: the table does not show it
            _filter = mo.vstack([
                mo.hstack([_filter, clear_filter_button], justify="start", align="center"),
                mo.md("The table does not show this filter after a reload. Filter the table again to change it, or clear it."),
            ])
    mo.vstack([
        mo.md(kit.describe_settings(map_meta["settings"])),
        mo.md(f"**Group events by:** `{path_column}`" if path_column != ak.CASE_ID else ""),
        mo.md(f"**Activity column:** `{drawn_activity_column}`" if drawn_activity_column != ak.ACTIVITY else ""),
        mo.md(
            "**Time frame:** " + " to ".join(
                (map_time_frame["start"] + pd.Timedelta(w, map_time_frame["unit"])).strftime("%Y-%m-%d %H:%M") for w in drawn_time_frame
            ) if drawn_time_frame else ""
        ),
        _filter,
        mo.md(kit.describe_map(map_meta)),
        mo.callout(
            mo.md(f"No event of these has a value for the attribute that makes up a path, so not drawn: {', '.join(f'`{a}`' for a in map_meta['left_out'])}."),
            kind="neutral",
        ) if map_meta["left_out"] else mo.md(""),
        # Marked as the map that was drawn, so that the nodes dragged in it are reported for it. No picture of the map is made
        # here: drawing one takes the notebook several seconds for every map and every drag, and the report draws the map from
        # the recorded step when it is exported.
        arrangement.watched(mo, _chart, state_of("map_figure"), pictured=False) if arrangement else _chart,
    ])
    return


if __name__ == "__main__":
    app.run()
