# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo>=0.25.2",
#     "pandas>=3.1.0",
#     "altair>=5.5",
#     "vegafusion>=2.0",
#     "pytz",
# ]
#
# [tool.marimo.opengraph]
# title = "00 Lecture - Initial Analysis"
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="00 Lecture - Initial Analysis")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Initial Event Log Analysis

    This notebook integrates a set of patterns for initial event log analysis that are useful for exploring the raw event log data
    before doing any specific process mining analysis such as behavioral, conformance, performance, or deviance analysis.

    Start by choosing the event log you want to analyse. If marimo shows a message that something failed, or the page stops responding,
    reload the page.
    """)
    return


@app.cell(hide_code=True)
def _():
    import altair as alt
    import marimo as mo
    import pandas as pd
    import shutil as _shutil
    import sys as _sys
    import tempfile as _tempfile
    import urllib.request as _request
    from pathlib import Path

    # large tables are charted (marimo's Visualize and Explore tabs) by vegafusion instead of being capped at 5,000 rows
    alt.data_transformers.enable("vegafusion")

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
    try:  # marimo-pmprov 0.16
        from provenance_widget.visualize import charts_of_this_layout
    except ImportError:
        charts_of_this_layout = None
    RAW_URL = "https://raw.githubusercontent.com/alvarobernal2412/bpm/main/"

    def project_file(relative, refresh=False):
        """A file of this project: next to the notebook in a local checkout, otherwise downloaded from the repository (molab
        delivers only the notebook file). The logs are downloaded once, the small files each time, so they are current."""
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

    # the helper modules of the analysis (the `lib/` folder of the repository), found next to the notebook or downloaded
    _lib = [project_file(f"lib/{name}.py", refresh=True) for name in (
        "temporal_characteristics_util", "data_quality_util", "display_util", "xes_reader", "initial_analysis_kit")]
    if str(_lib[0].parent) not in _sys.path:
        _sys.path.insert(0, str(_lib[0].parent))
    import display_util as du
    import initial_analysis_kit as ak
    import temporal_characteristics_util as tcu

    _ = du.enable_chart_builder()  # marimo's Visualize button on every table, also in the app (assigned: a bare call showed its True)

    return HERE, ak, charts_of_this_layout, du, mo, pd, project_file, tcu


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
def _(charts_of_this_layout, mo):
    # shows nothing. marimo keeps the charts built with Visualize in the browser, under the id of the cell that draws the table,
    # and an id is the position of the cell: a browser that saved charts before the cells of this notebook moved would show them
    # on other tables, so it starts without them (this notebook records nothing to put them back from).
    mo.ui.anywidget(charts_of_this_layout()) if charts_of_this_layout else None
    return


@app.cell(hide_code=True)
def _(mo):
    # The event logs a student can choose from: a name and the file of the log (a place in the repository), in the format it came in:
    # .xes, .csv (or .parquet). To offer other logs, change this list.
    DATASETS = {
        "DFG example": "data/dfg-example.xes",
        "Sepsis cases": "data/SepsisCases2020EventLog.xes",
        "Purchasing example": "data/Purchasing-Example.csv",
    }

    dataset_dropdown = mo.ui.dropdown(
        options=DATASETS,
        value=None,
        label="Choose an event log",
        allow_select_none=True,
    )
    dataset_dropdown
    return (dataset_dropdown,)


@app.cell(hide_code=True)
def _(ak, dataset_dropdown, du, mo, project_file):
    # Load the chosen event log in its own format. Colons in column names become underscores (they conflict with the marimo explorer).
    mo.stop(
        dataset_dropdown.value is None,
        mo.callout(mo.md("**Choose an event log to start the analysis.**"), kind="info"),
    )
    event_log_from_disk = ak.normalise_log(ak.read_log(project_file(dataset_dropdown.value)))
    mo.vstack([
        mo.md(f"**{len(event_log_from_disk):,}** events loaded. This is the event log as it was read from disk:"),
        du.table(event_log_from_disk),
    ])
    return (event_log_from_disk,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Log Initialization

    Initialize the event log with mandatory columns, time zone and -granularity.
    """)
    return


@app.cell(hide_code=True)
def _(ak, event_log_from_disk):
    # The format used for each timestamp column of the event log loaded from disk (shown in "Initial Timestamp attributes")
    timestamp_format_summary = ak.timestamp_formats(event_log_from_disk)
    return (timestamp_format_summary,)


@app.cell(hide_code=True)
def _(event_log_from_disk, mo, pd):
    # Select a timestamp attribute of the event log to inspect
    timestamp_columns = [
        col for col in event_log_from_disk.columns
        if isinstance(event_log_from_disk[col].dtype, pd.DatetimeTZDtype) or pd.api.types.is_datetime64_dtype(event_log_from_disk[col])
    ]

    timestamp_attribute_dropdown = mo.ui.dropdown(
        options=timestamp_columns,
        value=timestamp_columns[0] if timestamp_columns else None,
        label="Select a Timestamp attribute to inspect: ",
        searchable=True,
    )
    return timestamp_attribute_dropdown, timestamp_columns


@app.cell(hide_code=True)
def _(ak, event_log_from_disk, mo, timestamp_attribute_dropdown):
    # Show the granularity level of the encoded timestamps in the log, including whether timestamp components and timezone are constant
    timestamp_component_summary, timestamp_constant_prefixes = ak.timestamp_components(event_log_from_disk)
    timestamp_component_view, timestamp_prefix_view = ak.select_timestamp_component(
        timestamp_component_summary, timestamp_constant_prefixes, timestamp_attribute_dropdown.value
    )

    granularity_intro = mo.vstack([
        mo.md(
            f"Showing the precision of '{timestamp_attribute_dropdown.value}' and whether any timestamp "
            "elements are constant, based on the data recorded therein:"
        ),
        timestamp_attribute_dropdown,
    ])
    return granularity_intro, timestamp_component_view, timestamp_prefix_view


@app.cell(hide_code=True)
def _(ak, fully_filled_columns, mo, timestamp_columns):
    import pytz

    _common_timezones = pytz.common_timezones
    _default_timezone = "UTC" if "UTC" in _common_timezones else _common_timezones[0]

    GRANULARITY_LEVELS = ['year', 'month', 'day', 'hour', 'minute', 'second', 'millisecond', 'sub-millisecond']

    # Define mandatory columns to be user selected from all consistent columns
    _timestamp_options = [c for c in fully_filled_columns if c in set(timestamp_columns)]
    # what the log probably uses as case id, activity and completion time (the student can change them)
    _guess = ak.guess_mandatory(fully_filled_columns, _timestamp_options)

    timezone_dropdown = mo.ui.dropdown(
        options=_common_timezones,
        value=_default_timezone,
        label="Select Time Zone",
        allow_select_none=False,
        searchable=True,
    )

    granularity_normalization_dropdown = mo.ui.dropdown(
        options=GRANULARITY_LEVELS,
        value=None,
        label="Select granularity level",
        allow_select_none=True,
    )

    CASE_ID_dropdown = mo.ui.dropdown(
        options=fully_filled_columns,
        value=_guess["case_id"] if _guess["case_id"] in fully_filled_columns else fully_filled_columns[0],
        label="CASE ID column",
        allow_select_none=False,
        searchable=True,
    )

    COMPLETION_TIME_dropdown = mo.ui.dropdown(
        options=_timestamp_options,
        value=_guess["completion_time"] if _guess["completion_time"] in _timestamp_options else _timestamp_options[0],
        label="COMPLETION TIME column",
        allow_select_none=False,
        searchable=True,
    )

    ACTIVITY_dropdown = mo.ui.dropdown(
        options=fully_filled_columns,
        value=_guess["activity"] if _guess["activity"] in fully_filled_columns else fully_filled_columns[0],
        label="ACTIVITY column",
        allow_select_none=False,
        searchable=True,
    )
    return (
        ACTIVITY_dropdown,
        CASE_ID_dropdown,
        COMPLETION_TIME_dropdown,
        granularity_normalization_dropdown,
        timezone_dropdown,
    )


@app.cell(hide_code=True)
def _(
    ACTIVITY_dropdown,
    CASE_ID_dropdown,
    COMPLETION_TIME_dropdown,
    checkbox,
    granularity_normalization_dropdown,
    mo,
    timezone_dropdown,
):
    # the layout is its own cell: the checkbox changing must not rebuild (and so reset) the dropdowns
    log_initialization = mo.vstack([
        mo.md("Select a time zone to apply to all timestamp columns in the event log and case log:"),
        mo.hstack([timezone_dropdown], justify="start"),
        mo.md("(Optional) Select a granularity level to apply to all timestamp columns in the event log and case log:"),
        mo.hstack([granularity_normalization_dropdown], justify="start"),
        checkbox,
        mo.md("Select mandatory attributes from attributes that are fully filled:"),
        mo.hstack([CASE_ID_dropdown, COMPLETION_TIME_dropdown, ACTIVITY_dropdown])
    ])
    return (log_initialization,)


@app.cell(hide_code=True)
def _(
    CASE_ID,
    COMPLETION_TIME,
    ak,
    case_window_slider,
    checkbox,
    event_log_from_disk,
    granularity_normalization_dropdown,
    timezone_dropdown,
):
    # Log Initialization: time zone, granularity, time frame, constant and empty columns, duplicates, ordering, folding.
    initialized_event_log, initialization_messages, duplicate_event_instances = ak.initialize_log(
        event_log_from_disk,
        timezone_dropdown.value,
        granularity_normalization_dropdown.value,
        bool(checkbox.value),
        list(case_window_slider.value),
        CASE_ID,
        COMPLETION_TIME,
    )
    return duplicate_event_instances, initialization_messages, initialized_event_log


@app.cell(hide_code=True)
def _(CASE_ID, COMPLETION_TIME, ak, event_log_from_disk, mo):
    # Select a time frame; only cases that start and end within it are included in the event log
    DEFAULT_CASE_COUNT = 1500

    time_frame = ak.time_frame(event_log_from_disk, CASE_ID, COMPLETION_TIME, DEFAULT_CASE_COUNT)

    CASE_WINDOW_UNIT = time_frame["unit"]

    case_window_slider = mo.ui.range_slider(
        start=0,
        stop=time_frame["stop"],
        step=1,
        value=[0, time_frame["default"]],
        label=f"Time frame in {'days' if CASE_WINDOW_UNIT == 'D' else 'hours'} after {time_frame['start']}",
        full_width=True,
        debounce=True,
    )

    time_frame_selector = mo.vstack([
        mo.md("Select a time frame. Only cases that are fully contained within it are "
            f"included for analysis. The initial selection covers the first {DEFAULT_CASE_COUNT} cases."
        ),
        case_window_slider
    ])
    return case_window_slider, time_frame_selector


@app.cell(hide_code=True)
def _(CASE_ID, COMPLETION_TIME, ak, initialized_event_log):
    # Compute ordering information: are events ordered by completion time within each case and across the log?
    case_ordering_summary = log_ordering_summary = None  # no case lies within the selected time frame
    if not initialized_event_log.empty:
        case_ordering_summary, log_ordering_summary = ak.ordering_summaries(initialized_event_log, CASE_ID, COMPLETION_TIME)
    return case_ordering_summary, log_ordering_summary


@app.cell(hide_code=True)
def _(event_log_from_disk, mo):
    # marimo keeps the charts built with Visualize per cell, so tables that share a cell share their charts. The tabs are
    # therefore only the strip: what a tab shows is drawn by a cell of its own below, one table per cell.
    _ = event_log_from_disk  # the strip appears with the log, as its tabs do
    initialization_tab = mo.ui.tabs({_name: "" for _name in (
        "Log Initialization", "Initialization Summary", "Time Frame", "Granularity Analysis", "Ordering Info",
        "Initial Timestamp attributes")})
    granularity_tab = mo.ui.tabs({"Component analysis": "", "Constant prefixes": ""})
    initialization_tab
    return granularity_tab, initialization_tab


@app.cell(hide_code=True)
def _(initialization_tab, log_initialization):
    log_initialization if initialization_tab.value == "Log Initialization" else None
    return


@app.cell(hide_code=True)
def _(duplicate_event_instances, du, initialization_messages, initialization_tab, mo):
    _output = None
    if initialization_tab.value == "Initialization Summary":
        _output = [mo.md("### Summary of the Initialization"), mo.md("\n".join(f"- {_message}" for _message in initialization_messages))]
        if not duplicate_event_instances.empty:
            _output.append(mo.md("The following events had duplicates that have been removed, retaining only one:"))
            _output.append(du.table(duplicate_event_instances))
    mo.vstack(_output) if _output else None
    return


@app.cell(hide_code=True)
def _(initialization_tab, time_frame_selector):
    time_frame_selector if initialization_tab.value == "Time Frame" else None
    return


@app.cell(hide_code=True)
def _(granularity_intro, granularity_tab, initialization_tab, mo):
    mo.vstack([granularity_intro, granularity_tab]) if initialization_tab.value == "Granularity Analysis" else None
    return


@app.cell(hide_code=True)
def _(du, granularity_tab, initialization_tab, timestamp_component_view):
    du.table(timestamp_component_view) if (initialization_tab.value, granularity_tab.value) == ("Granularity Analysis", "Component analysis") else None
    return


@app.cell(hide_code=True)
def _(du, granularity_tab, initialization_tab, timestamp_prefix_view):
    du.table(timestamp_prefix_view) if (initialization_tab.value, granularity_tab.value) == ("Granularity Analysis", "Constant prefixes") else None
    return


@app.cell(hide_code=True)
def _(case_ordering_summary, du, initialization_tab, mo):
    _shown = None
    if initialization_tab.value == "Ordering Info":
        _shown = mo.md("_No case lies within the selected time frame._") if case_ordering_summary is None else du.table(case_ordering_summary)
    _shown
    return


@app.cell(hide_code=True)
def _(du, initialization_tab, log_ordering_summary):
    du.table(log_ordering_summary) if initialization_tab.value == "Ordering Info" and log_ordering_summary is not None else None
    return


@app.cell(hide_code=True)
def _(du, initialization_tab, mo, timestamp_format_summary):
    mo.vstack([
        mo.md("Showing the format of each timestamp column in the initial event log loaded from disk, if unambiguously detected from the data recorded therein:"),
        du.table(timestamp_format_summary),
    ]) if initialization_tab.value == "Initial Timestamp attributes" else None
    return


@app.cell(hide_code=True)
def _(initialized_event_log, mo):
    # an empty time frame has nothing to analyse: say so instead of failing in every cell below
    mo.stop(
        initialized_event_log.empty,
        mo.callout(mo.md("No case lies completely within the selected time frame. Widen the time frame."), kind="warn"),
    )
    event_log = initialized_event_log
    return (event_log,)


@app.cell(hide_code=True)
def _(event_log_from_disk, mo):
    # identify columns that are filled for every row
    fully_filled_columns = [ col for col in event_log_from_disk.columns if event_log_from_disk[col].notna().all() ]

    _constant_columns = [ col for col in fully_filled_columns if event_log_from_disk[col].nunique() <= 1]
    fully_filled_columns = [ col for col in fully_filled_columns if col not in _constant_columns ]

    checkbox = mo.ui.checkbox(label="Enforce global ordering of the event log by completion time")
    return checkbox, fully_filled_columns


@app.cell(hide_code=True)
def _(ACTIVITY_dropdown, CASE_ID_dropdown, COMPLETION_TIME_dropdown):
    # Name the mandatory attributes once. Everything downstream reads these rather than the dropdowns.
    CASE_ID = CASE_ID_dropdown.value
    ACTIVITY = ACTIVITY_dropdown.value
    COMPLETION_TIME = COMPLETION_TIME_dropdown.value
    return ACTIVITY, CASE_ID, COMPLETION_TIME


@app.cell(hide_code=True)
def _(ACTIVITY, CASE_ID, COMPLETION_TIME, ak, event_log):
    # Based on selected mandatory attributes, classify each attribute as mandatory, standard, or else
    attribute_classes = ak.classify_attributes(event_log, CASE_ID, ACTIVITY, COMPLETION_TIME)

    MANDATORY_COLUMNS = attribute_classes["mandatory"]
    STANDARD_COLUMNS = attribute_classes["standard"]
    CASE_FEATURE_COLUMNS = attribute_classes["case_features"]
    activity_list = attribute_classes["activity_list"]
    activity_stats = attribute_classes["activity_stats"]
    return (
        CASE_FEATURE_COLUMNS,
        MANDATORY_COLUMNS,
        STANDARD_COLUMNS,
        activity_list,
        activity_stats,
        attribute_classes,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Events View

    The following tables extract different views from the event log. A _global_ attribute is available in each event. A _local_ attribute is available typically in one, sometimes in more than one activity schema. The _Case Inspection_ view is optimized for inspecting one or  more cases with event-specific data being folded into a single column. In the _Case Log_ view each row is a case of the log and only attributes that do never change in a case are shown. The _Raw Events_ view shows the raw, full event log for completeness only.

    Each view is equipped with Marimo-built features such as "_Visualize_" and "_Explore_".
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    _sample_enrichment = "# case_log['CRP_count'] = event_log.groupby(CASE_ID)['CRP'].count()"

    # the code that was submitted last (what the case log is built with)
    get_enrichment_code, set_enrichment_code = mo.state("")
    applied_enrichment = {"code": None}  # the code the case log was last built with successfully

    case_enrichment_code_editor = mo.ui.code_editor(
        value=_sample_enrichment,
        language="python",
        label="Write your code here")
    return applied_enrichment, case_enrichment_code_editor, get_enrichment_code, set_enrichment_code


@app.cell(hide_code=True)
def _(case_enrichment_code_editor, mo, set_enrichment_code):
    _intro = mo.md("Enrich the case log by hand.  The same, one level up. case_log carries the base case attributes, the applied case enrichments and the case-level attributes found in the log.")

    case_enrichment_submit_button = mo.ui.button(
        label="Submit", on_click=lambda _: set_enrichment_code(case_enrichment_code_editor.value)
    )
    mo.vstack([_intro, case_enrichment_code_editor, case_enrichment_submit_button])
    return


@app.cell(hide_code=True)
def _(
    ACTIVITY,
    CASE_FEATURE_COLUMNS,
    CASE_ID,
    COMPLETION_TIME,
    ak,
    applied_enrichment,
    event_log,
    get_enrichment_code,
    mo,
):
    # Define case log; the code you submit enriches it
    _code = get_enrichment_code() or None
    _error = None
    if _code:
        try:
            ak.build_case_log(event_log, CASE_ID, ACTIVITY, COMPLETION_TIME, CASE_FEATURE_COLUMNS, _code)
        except Exception as _problem:  # the student's code is theirs: show what went wrong, keep the earlier enrichment
            _error, _code = _problem, applied_enrichment["code"]
    applied_enrichment["code"] = _code

    case_log = ak.build_case_log(event_log, CASE_ID, ACTIVITY, COMPLETION_TIME, CASE_FEATURE_COLUMNS, _code)
    mo.callout(
        mo.md(f"The new enrichment code was not applied (the case log keeps the last working one): `{type(_error).__name__}: {_error}`"),
        kind="danger",
    ) if _error else None
    return (case_log,)


@app.cell(hide_code=True)
def _(activity_list, mo):
    activity_multiselect = mo.ui.multiselect(
        options=activity_list,
        value=activity_list[:1] if len(activity_list) >= 1 else activity_list,
        label="Select activities to see local attributes",
    )
    hide_case_features_checkbox = mo.ui.checkbox(label="Hide attributes that are also case-level attributes")
    return activity_multiselect, hide_case_features_checkbox


@app.cell(hide_code=True)
def _(
    activity_multiselect,
    ak,
    attribute_classes,
    event_log,
    hide_case_features_checkbox,
):
    local_attribute_table = ak.local_attribute_view(
        event_log, list(activity_multiselect.value), attribute_classes, bool(hide_case_features_checkbox.value)
    )
    return (local_attribute_table,)


@app.cell(hide_code=True)
def _(ak, attribute_classes, event_log, mo):
    # The strip of the Events View; each view is drawn by a cell of its own below (one table per cell, see the tabs above).
    event_views = ak.event_views(event_log, attribute_classes)
    events_tab = mo.ui.tabs({_name: "" for _name in (
        "Global Attributes", "Local Attributes", "Case Inspection", "Case Log", "Raw Events")})
    events_tab
    return event_views, events_tab


@app.cell(hide_code=True)
def _(du, event_views, events_tab):
    # du.table rather than the frames themselves: a timedelta column pushes marimo's chart builder off the Arrow path.
    du.table(event_views["global"]) if events_tab.value == "Global Attributes" else None
    return


@app.cell(hide_code=True)
def _(activity_multiselect, du, events_tab, hide_case_features_checkbox, local_attribute_table, mo):
    mo.vstack([
        mo.md("Select one or more activities to view only the data attributes that are common to their schemas:"),
        activity_multiselect,
        hide_case_features_checkbox,
        du.table(local_attribute_table, pagination=True, page_size=15)
        if activity_multiselect.value
        else mo.md("_No activities selected._"),
    ]) if events_tab.value == "Local Attributes" else None
    return


@app.cell(hide_code=True)
def _(du, event_views, events_tab):
    du.table(event_views["inspection"]) if events_tab.value == "Case Inspection" else None
    return


@app.cell(hide_code=True)
def _(case_log, du, events_tab):
    du.table(case_log) if events_tab.value == "Case Log" else None
    return


@app.cell(hide_code=True)
def _(du, event_log, events_tab):
    du.table(event_log) if events_tab.value == "Raw Events" else None
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Activity Schemas View

    A _schema_ of a given activity is the set of all attributes such that at least one event of the activity has a value for that attribute. Therefore, each _global_ attribute is in each schema. _Local_ attributes can be _shared_ between the schema of two or more activities or _exclusive_ to one activity schema.
    """)
    return


@app.cell(hide_code=True)
def _(
    ACTIVITY,
    CASE_ID,
    MANDATORY_COLUMNS,
    STANDARD_COLUMNS,
    activity_stats,
    ak,
    event_log,
):
    schema_usages, partial_schema_usages = ak.schema_views(
        event_log, CASE_ID, ACTIVITY, MANDATORY_COLUMNS, STANDARD_COLUMNS, activity_stats
    )
    return partial_schema_usages, schema_usages


@app.cell(hide_code=True)
def _(mo, schema_usages):
    # Show schemas, schema population, and overlaps: the strip here, each table in a cell of its own below
    _ = schema_usages  # the strip appears with the tables, as its tabs do
    schemas_tab = mo.ui.tabs({"Activity Schemas": "", "Schema Overlaps": ""})
    schemas_tab
    return (schemas_tab,)


@app.cell(hide_code=True)
def _(du, schema_usages, schemas_tab):
    du.table(schema_usages[['incidence', 'local_attributes', 'missing_values']]) if schemas_tab.value == "Activity Schemas" else None
    return


@app.cell(hide_code=True)
def _(du, partial_schema_usages, schemas_tab):
    du.table(partial_schema_usages[(partial_schema_usages != 0).any(axis=1)]) if schemas_tab.value == "Schema Overlaps" else None
    return


if __name__ == "__main__":
    app.run()
