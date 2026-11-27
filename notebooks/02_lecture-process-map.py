# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo>=0.25.2",
#     "pandas>=3.1.0",
#     "anywidget",
#     "linear-continuous-process-mapper>=0.2.0",
#     "plotly>=7.1.0",
# ]
#
# [tool.marimo.opengraph]
# title = "02 Lecture - Process Map"
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="02 Lecture - Process Map")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Map explorer: Sepsis cases

    Draw process maps of the Sepsis cases event log: choose the activities and the settings, then press **Refresh visualization**.

    Nothing is saved in this notebook: when you close or reload the page, it starts again from the first map. If marimo shows a message
    that something failed, or the page stops responding, reload the page.
    """)
    return


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import pandas as pd
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
        "temporal_characteristics_util", "data_quality_util", "display_util", "xes_reader", "initial_analysis_kit")]
    if str(_lib[0].parent) not in _sys.path:
        _sys.path.insert(0, str(_lib[0].parent))
    import display_util as du
    import initial_analysis_kit as ak

    return HERE, ak, du, kit, mo, pd, project_file


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
def _(ak, mo, project_file):
    # The event log of this notebook (a place in the repository). Colons in column names become underscores, as in the other notebooks.
    SEPSIS = "data/SepsisCases2020EventLog.xes"

    event_log = ak.normalise_log(ak.read_log(project_file(SEPSIS)))
    mo.md(f"**{len(event_log):,}** events of **{event_log[ak.CASE_ID].nunique():,}** cases loaded.")
    return (event_log,)


@app.cell(hide_code=True)
def _(du, event_log, mo):
    # The event log as a table. Its column filters are the filter of the map: Refresh visualization takes them (`ak.table_filters`).
    event_table = du.table(event_log, page_size=5)
    mo.vstack([
        mo.md("## Event log"),
        event_table,
        mo.md("Filter the table with the menu of a column; the map uses the filter when you press Refresh visualization."),
    ])
    return (event_table,)


@app.cell(hide_code=True)
def _(ak, event_log, get_drawn, map_time_frame):
    # The log the map is drawn from: what the filter of the drawn settings keeps (the log itself without a filter), and where its
    # time frame counts from: the start of the whole log, whose slider it is.
    drawn_filter = get_drawn().get("filter") or []
    map_log = ak.filter_log(event_log, drawn_filter)
    map_origin = ak.window_origin(map_time_frame) if map_log is not event_log else None
    return drawn_filter, map_log, map_origin


@app.cell(hide_code=True)
def _(ak, event_log, kit, mo):
    # The controls are built from the whole log, not from what the filter keeps: a change of the filter does not make them again
    # (and lose what was set). The map and the counts are drawn from the filtered log; an activity that the filter left out is named
    # under the map.
    # "Group events by": the attributes whose values can make up a path; the case id is the normal one
    explorer_notions = {("Case ID" if c == ak.CASE_ID else c): c for c in ak.path_attribute_options(event_log)}
    # "Activity column": the column whose values are the nodes of the map
    activity_column_dropdown = mo.ui.dropdown(
        options=ak.activity_column_options(event_log), value=ak.ACTIVITY, label="Activity column", allow_select_none=False,
    )
    # "Time frame": only the cases that lie completely inside it are drawn. The slider is a control of its own, so choosing another
    # activity column does not move it.
    map_time_frame = ak.time_frame(event_log, ak.CASE_ID, ak.TIMESTAMP)
    time_frame_slider = mo.ui.range_slider(
        start=0, stop=map_time_frame["stop"], step=1, value=[0, map_time_frame["stop"]], full_width=True, debounce=True,
        label=f"Time frame in {'days' if map_time_frame['unit'] == 'D' else 'hours'} after {map_time_frame['start']}",
    )
    # drawn: what the map shows (changed by Refresh). The explorer starts on the 5 most frequent activities, a map small enough to
    # read at once. It does not depend on the activity column dropdown, so choosing another column changes nothing until Refresh is pressed.
    initial_settings = kit.normalise_settings(
        {
            "activities": sorted(event_log[ak.ACTIVITY].value_counts().index[:5]),
            "case_notion": ak.CASE_ID,
            "activity_column": ak.ACTIVITY,
            "time_frame": None,  # None is the whole log
            "filter": [],  # the column filters of the table, taken by Refresh
        }
    )
    get_drawn, set_drawn = mo.state(initial_settings)
    # The controls that do not depend on the activity column (see `kit.KEPT_CONTROLS`), as the analyst last set them. A plain dict, not
    # a state: it is filled by the cell below and read by the cell that builds the controls, which must not run again when it changes.
    # (it also keeps the selected activities and the fold rows, for as long as the activity column is the same one).
    kept_controls = {}
    # "Add fold" raises a counter; the cell that builds the controls reads it and makes the controls again with one more fold row.
    get_fold_adds, set_fold_adds = mo.state(0)
    add_fold_button = mo.ui.button(label="Add fold", on_click=lambda _: set_fold_adds(lambda n: n + 1))
    return activity_column_dropdown, add_fold_button, explorer_notions, get_drawn, get_fold_adds, initial_settings, kept_controls, map_time_frame, set_drawn, time_frame_slider


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
def _(activity_column, ak, event_table, explorer_names, kit, map_controls, map_time_frame, mo, set_drawn, time_frame_slider):
    refresh_button = mo.ui.button(
        label="Refresh visualization", kind="success",
        on_click=lambda _: set_drawn({
            **kit.settings_from(map_controls.value, explorer_names), "activity_column": activity_column,
            "time_frame": ak.time_frame_window(time_frame_slider.value, map_time_frame["stop"]),
            "filter": ak.table_filters(event_table),
        }),
    )
    return (refresh_button,)


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
def _(ak, event_log, get_drawn, kit, map_log, map_origin, mo):
    _settings = get_drawn()
    _problems = kit.fold_problems(_settings)
    mo.stop(bool(_problems), mo.callout(mo.md("  \n".join(_problems)), kind="danger"))
    mo.stop(_settings["activities"] == [], mo.callout(mo.md("Select at least one activity."), kind="warn"))
    path_column = _settings["case_notion"]  # "Group events by": the attribute whose values make up a path
    drawn_activity_column = _settings["activity_column"]
    # the case, activity and time columns under the names the map library reads, for the drawn settings
    drawn_time_frame = _settings["time_frame"]
    # the map is drawn from what the filter keeps: it must still have the columns that make up the paths and the nodes
    _problem = ak.filter_problem(event_log, map_log, needed=[path_column, drawn_activity_column])
    mo.stop(_problem is not None, mo.callout(mo.md(_problem or ""), kind="warn"))
    mo.stop(
        ak.cases_in_time_frame(map_log, drawn_time_frame, map_origin)[0] == 0,
        mo.callout(mo.md("No case lies completely within the time frame. Widen it and press Refresh visualization."), kind="warn"),
    )
    lcm_log = ak.to_lcm_log(map_log, path_column, drawn_activity_column, drawn_time_frame, map_origin)
    try:
        map_figure, map_meta = kit.draw_map(
            lcm_log, _settings["activities"], _settings["map_type"], _settings["allow_loops"],
            _settings["show_empty"], _settings["folds"], "application", 900,  # the log's own case column is already the chosen one
            room=(100, 140, 110),  # the rings of the loops reach above, below and left of the nodes: with less room they are cut off
        )
    except ValueError as _error:
        _available = ", ".join(f"`{a}`" for a in sorted(lcm_log["concept:name"].unique()))
        _occur = f" The activities that occur when events are grouped by `{path_column}` are: {_available}." if _available else ""
        mo.stop(True, mo.callout(mo.md(f"{_error}{_occur}"), kind="danger"))
    return drawn_activity_column, drawn_time_frame, map_figure, map_meta, path_column


@app.cell(hide_code=True)
def _(ak, drawn_activity_column, drawn_filter, drawn_time_frame, event_log, kit, map_figure, map_log, map_meta, map_time_frame, mo, path_column, pd):
    mo.vstack([
        mo.md(kit.describe_settings(map_meta["settings"])),
        mo.md(f"**Group events by:** `{path_column}`" if path_column != ak.CASE_ID else ""),
        mo.md(f"**Activity column:** `{drawn_activity_column}`" if drawn_activity_column != ak.ACTIVITY else ""),
        mo.md(
            "**Time frame:** " + " to ".join(
                (map_time_frame["start"] + pd.Timedelta(w, map_time_frame["unit"])).strftime("%Y-%m-%d %H:%M") for w in drawn_time_frame
            ) if drawn_time_frame else ""
        ),
        mo.md(
            f"**Filter:** {ak.filter_words(drawn_filter)} · {map_log[ak.CASE_ID].nunique():,} of "
            f"{event_log[ak.CASE_ID].nunique():,} cases are kept ({len(map_log):,} events)."
        ) if drawn_filter else mo.md(""),
        mo.md(kit.describe_map(map_meta)),
        mo.as_html(map_figure),
    ])
    return


if __name__ == "__main__":
    app.run()
