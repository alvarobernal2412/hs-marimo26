# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo>=0.25.2",
#     "pandas>=3.1.0",
#     "anywidget",
#     "linear-continuous-process-mapper>=0.1.0",
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
        "temporal_characteristics_util", "data_quality_util", "xes_reader", "initial_analysis_kit")]
    if str(_lib[0].parent) not in _sys.path:
        _sys.path.insert(0, str(_lib[0].parent))
    import initial_analysis_kit as ak

    return ak, kit, mo, project_file


@app.cell(hide_code=True)
def _(ak, mo, project_file):
    # The event log of this notebook (a place in the repository). Colons in column names become underscores, as in the other notebooks.
    SEPSIS = "data/SepsisCases2020EventLog.xes"

    event_log = ak.normalise_log(ak.read_log(project_file(SEPSIS)))
    # the case, activity and time columns under the names the map library reads; a path of the map is a case
    lcm_log = ak.to_lcm_log(event_log)
    mo.md(f"**{len(event_log):,}** events of **{event_log[ak.CASE_ID].nunique():,}** cases loaded.")
    return event_log, lcm_log


@app.cell(hide_code=True)
def _(ak, event_log, kit, mo):
    explorer_names = sorted(event_log[ak.ACTIVITY].unique())
    # draft: what the controls are built from; drawn: what the map shows (changed by Refresh). The explorer starts on the 5 most
    # frequent activities, a map small enough to read at once.
    _settings = kit.normalise_settings({"activities": sorted(event_log[ak.ACTIVITY].value_counts().index[:5])})
    get_draft, set_draft = mo.state(_settings)
    get_drawn, set_drawn = mo.state(_settings)
    return explorer_names, get_draft, get_drawn, set_drawn


@app.cell(hide_code=True)
def _(explorer_names, get_draft, kit, mo):
    # a path is always a case here, so the "Each path is" control has one option and is not shown
    map_controls = kit.map_controls(mo, explorer_names, get_draft(), {"A case": "application"})
    return (map_controls,)


@app.cell(hide_code=True)
def _(explorer_names, kit, map_controls, mo, set_drawn):
    refresh_button = mo.ui.button(
        label="Refresh visualization", kind="success",
        on_click=lambda _: set_drawn(kit.settings_from(map_controls.value, explorer_names)),
    )
    return (refresh_button,)


@app.cell(hide_code=True)
def _(explorer_names, get_drawn, kit, map_controls, mo, refresh_button):
    _current = kit.settings_from(map_controls.value, explorer_names)
    kit.controls_layout(
        mo, map_controls, mo.md(""), refresh_button,
        kit.refresh_status(mo, _current, get_drawn()), show_case_notion=False,
    )
    return


@app.cell(hide_code=True)
def _(get_drawn, kit, lcm_log, mo):
    _settings = get_drawn()
    _problems = kit.fold_problems(_settings)
    mo.stop(bool(_problems), mo.callout(mo.md("  \n".join(_problems)), kind="danger"))
    mo.stop(_settings["activities"] == [], mo.callout(mo.md("Select at least one activity."), kind="warn"))
    map_figure, map_meta = kit.draw_map(
        lcm_log, _settings["activities"], _settings["map_type"], _settings["allow_loops"],
        _settings["show_empty"], _settings["folds"], "application", 620,
    )
    return map_figure, map_meta


@app.cell(hide_code=True)
def _(kit, map_figure, map_meta, mo):
    mo.vstack([
        mo.md(kit.describe_settings(map_meta["settings"])),
        mo.md(kit.describe_map(map_meta)),
        mo.as_html(map_figure),
    ])
    return


if __name__ == "__main__":
    app.run()
