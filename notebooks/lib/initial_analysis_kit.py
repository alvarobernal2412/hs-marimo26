"""The analysis stages of the initial-analysis notebooks, as plain functions.

`01_assignment-initial-analysis.py` runs each of them through `record(...)` (so a stage and the widget values that drove it become one recorded
step); `initial-review.py` replays the stored results. They are ports of the cells of the exploratory `initial-analysis` notebook,
working on the enriched Dhana LoanApplication log (colon-free column names, see `scripts/xes_to_parquet.py`). None of them changes
its input.

`lib/` is put on `sys.path` by the notebooks, so the sibling helper modules are imported flat.
"""
from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import signal
import sys
import tempfile
import threading
import time
from pathlib import Path

import pandas as pd

import data_quality_util as dqu
import temporal_characteristics_util as tcu

CASE_ID = "case_concept_name"
ACTIVITY = "concept_name"
TIMESTAMP = "time_timestamp"
LIFECYCLE = "lifecycle_transition"
ACTIVITY_EXTENDED = "activity_extended"  # "<activity>_<lifecycle>": an underscore, not a comma, so that a CSV export keeps its columns
DHANA = "data/dhana-loan-application.parquet"  # not public and not in the package: the launcher fetches it (launcher/coursefiles.py)
MISSING_LOG = (
    "**The course event log is not on this computer yet.** Close the window that opened when you started, double-click "
    "**Start** again and enter the course code your teachers gave you. If you have no code, ask your teachers."
)
HISTORY_NAME = "Dhana loan application initial analysis"
MAP_EXPLORER_HISTORY_NAME = "Dhana loan application map explorer"

# The identifiers the notebooks save under on the course server (course > student > notebook).
INITIAL_ANALYSIS_NOTEBOOK = "initial-analysis"
MAP_EXPLORER_NOTEBOOK = "map-explorer"
OFFER_ID = "OfferID"
CREATE_OFFER = "O_Create Offer"

# a step that needs these can never lose them to the "constant column" rule (a log with one case has a constant case id)
_PROTECTED = (CASE_ID, ACTIVITY, TIMESTAMP)


def _is_timestamp(series: pd.Series) -> bool:
    return isinstance(series.dtype, pd.DatetimeTZDtype) or pd.api.types.is_datetime64_dtype(series)


def log_is_missing(folder) -> bool:
    """Whether the course log is absent from the notebooks' folder (the student started without entering the course code)."""
    return not (Path(folder) / DHANA).is_file()


LIFECYCLE_STATE = "lifecycle_state"
# Whether the activity is being worked on after the event: "on" from a start or a resume, "off" otherwise. Other values have no state.
LIFECYCLE_STATES = {
    "start": "on", "resume": "on",
    "complete": "off", "suspend": "off", "schedule": "off", "withdraw": "off", "ate_abort": "off",
}


def add_lifecycle_state(log: pd.DataFrame) -> pd.DataFrame:
    """A copy of `log` with the `lifecycle_state` column ("on" or "off", see `LIFECYCLE_STATES`) right after `lifecycle_transition`;
    a transition that is not in that table, or is missing, has no state. A log without a lifecycle, or that has the column already,
    is returned as it is."""
    if LIFECYCLE not in log.columns or LIFECYCLE_STATE in log.columns:
        return log
    state = log[LIFECYCLE].map(LIFECYCLE_STATES).astype("string")
    out = log.copy()
    out.insert(list(out.columns).index(LIFECYCLE) + 1, LIFECYCLE_STATE, state)
    return out


def load_event_log(path) -> pd.DataFrame:
    """The Dhana log, from its `.parquet` (what the notebooks use) or from the `.xes` of it (keys already the notebooks' column names)."""
    path = Path(path)
    if path.suffix.lower() == ".xes":
        from xes_reader import read_xes

        log = read_xes(str(path), verbatim=True)
        if ACTIVITY_EXTENDED in log.columns:  # where the parquet has it: last
            log = log[[c for c in log.columns if c != ACTIVITY_EXTENDED] + [ACTIVITY_EXTENDED]]
        return add_lifecycle_state(log)
    return add_lifecycle_state(pd.read_parquet(path))


def timestamp_formats(log: pd.DataFrame) -> pd.DataFrame:
    """The format of each timestamp column, where the recorded data tells it unambiguously."""
    rows = []
    for col in [c for c in log.columns if _is_timestamp(log[c])]:
        result = tcu.infer_timestamp_format_from_column(log[col])
        rows.append({
            "Timestamp column": col,
            "Status": result["status"],
            "Format": tcu.format_to_human(result["format"]),
            "Example": tcu.get_example_timestamp(log[col], result["format"]),
            "Pattern": result["format"],
        })
    return pd.DataFrame(rows)


def time_frame(log: pd.DataFrame, case_id: str, completion_time: str, default_case_count: int = 1500) -> dict:
    """What the time-frame slider is built from: `start` of the log, the `unit` ('D', or 'h' for logs shorter than two days), the
    slider's `stop` and the `default` end that covers the first `default_case_count` cases."""
    bounds = tcu.get_case_time_bounds(log, case_id, completion_time)
    start, last = bounds["min"].min(), bounds["max"].max()
    unit = "D" if (last - start) >= pd.Timedelta(days=2) else "h"
    length = pd.Timedelta(1, unit)
    default_end = tcu.get_end_time_of_nth_case(bounds, default_case_count)
    return {
        "start": start,
        "unit": unit,
        "stop": int((last - start) / length) + 1,
        "default": int((default_end - start) / length) + 1,
    }


def initialize_log(
    log: pd.DataFrame, timezone: str, granularity: str | None, enforce_order: bool, window: tuple, case_id: str, completion_time: str
) -> tuple[pd.DataFrame, list[str], pd.DataFrame]:
    """Time zone, granularity, time frame, constant/empty columns, duplicates, optional global ordering, folded data.

    `window` is the slider's (from, to) in the units of `time_frame`. Returns the initialized log, what was done (one line each) and
    one kept instance per group of duplicate events."""
    out = log.copy()
    messages: list[str] = []
    frame = time_frame(out, case_id, completion_time)

    for col in out.columns:
        if isinstance(out[col].dtype, pd.DatetimeTZDtype):
            out[col] = out[col].dt.tz_convert(timezone)
            messages.append(f"Converted column '{col}' to timezone {timezone}")

    if granularity is not None:
        if granularity not in tcu._FREQ_ALIASES:
            messages.append(f"Granularity normalization to '{granularity}' is currently not supported.")
        else:
            for col in [c for c in out.columns if _is_timestamp(out[c])]:
                rounded = out[col].dt.round(tcu._FREQ_ALIASES[granularity])
                messages.append(f"Rounded {int((rounded != out[col]).sum())}/{len(out)} values in '{col}' to the nearest {granularity}")
                out[col] = rounded

    start = frame["start"] + pd.Timedelta(window[0], frame["unit"])
    end = frame["start"] + pd.Timedelta(window[1], frame["unit"])
    cases_before = out[case_id].nunique()
    out = tcu.filter_cases_within_window(out, case_id, completion_time, start, end)
    messages.append(f"Time frame {start} to {end}: kept {out[case_id].nunique()} of {cases_before} cases ({len(out)} events)")
    if out.empty:
        return out.assign(folded_data=pd.Series(dtype=object)), messages, dqu.summarize_duplicate_events(out)

    filled = [c for c in out.columns if out[c].notna().all()]
    constant = [c for c in filled if out[c].nunique() <= 1 and c not in _PROTECTED and c not in (case_id, completion_time)]
    for col in constant:
        values = out[col].unique()
        messages.append(f"Dropped constant column '{col}' with value: {values[0] if len(values) else None}")
    out = out.drop(columns=constant)
    empty = [c for c in out.columns if c not in filled and out[c].notna().sum() == 0]
    for col in empty:
        messages.append(f"Dropped empty column '{col}'")
    out = out.drop(columns=empty)
    inconsistent = [c for c in out.columns if c not in filled and c not in empty]

    duplicates = dqu.summarize_duplicate_events(out)
    if not duplicates.empty:
        before = len(out)
        out = dqu.remove_duplicate_events(out)
        messages.append(f"Removed {before - len(out)} duplicate events in {len(duplicates)} groups of identical events")

    if enforce_order:
        out = out.assign(original_order=range(len(out))).sort_values(by=[completion_time, "original_order"]).reset_index(drop=True)
        assert out[completion_time].is_monotonic_increasing
        messages.append("All events in the log are now globally ordered.")

    records = out[inconsistent].to_dict("records") if inconsistent else [{} for _ in range(len(out))]
    out["folded_data"] = pd.Series([{k: v for k, v in r.items() if pd.notna(v)} or None for r in records], index=out.index, dtype=object)
    return out, messages, duplicates


def ordering_summaries(log: pd.DataFrame, case_id: str, completion_time: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    return tcu.analyze_event_ordering(log, case_id, completion_time)


def classify_attributes(log: pd.DataFrame, case_id: str, activity: str, completion_time: str) -> dict:
    """Mandatory, standard (filled by every activity), case-level and per-activity attributes of the log."""
    mandatory = [case_id, activity, completion_time]
    stats = log[activity].value_counts()
    attrs = log.drop(columns=["folded_data"], errors="ignore")
    counts = attrs.groupby(activity).count().reindex(stats.index)
    standard = [c for c in counts.columns if (counts[c] != 0).all() and c not in mandatory]
    schema = {
        a: [c for c in counts.columns if counts.loc[a, c] != 0 and c not in mandatory + standard] for a in stats.index
    }
    per_case = attrs.drop(columns=[case_id]).groupby(attrs[case_id]).nunique()
    case_features = [c for c in per_case.columns if per_case[c].max() <= 1]
    return {
        "mandatory": mandatory,
        "standard": standard,
        "case_features": case_features,
        "activity_schema": schema,
        "activity_list": list(stats.index),
        "activity_stats": stats,
    }


def build_case_log(
    log: pd.DataFrame, case_id: str, activity: str, completion_time: str, case_features: list, enrichment_code: str | None = None
) -> pd.DataFrame:
    """One row per case: start, end, duration, number of events and the case-level attributes; then the student's enrichment code, if any,
    run with `case_log`, `event_log`, `pd` and the names of `enrichment_names` (`CASE_ID`, ...) in scope. An error in that code
    propagates."""
    grouped = log.groupby(case_id)
    cases = grouped.agg(
        start_time=(completion_time, "first"), end_time=(completion_time, "last"), no_of_events=(activity, "count")
    )
    cases.insert(2, "duration", cases["end_time"] - cases["start_time"])  # right after end_time
    extra = [c for c in case_features if c not in cases.columns and c != "folded_data"]
    if extra:
        folded = grouped[extra].first()
        for col in extra:
            cases[col] = folded[col]
    if enrichment_code:
        cases = run_enrichment(cases, log, enrichment_code, enrichment_names(case_id, activity, completion_time))["case_log"]
    return cases


def enrichment_names(case_id: str = CASE_ID, activity: str = ACTIVITY, completion_time: str = TIMESTAMP) -> dict:
    """The notebook's variables that the student's code can use: the names of the three mandatory columns, as the notebook has
    them (what the student picked, or the course's own). Add a name here and every notebook offers it."""
    return {"CASE_ID": case_id, "ACTIVITY": activity, "COMPLETION_TIME": completion_time}


def run_enrichment(case_log, event_log: pd.DataFrame, code: str, names: dict | None = None) -> dict:
    """Run the student's enrichment code with `case_log`, `event_log`, `pd` and `names` (default: `enrichment_names()`) in scope;
    returns the scope the code left behind."""
    scope = {**(enrichment_names() if names is None else names), "case_log": case_log, "pd": pd, "event_log": event_log}
    exec(code, scope)
    return scope


def schema_views(
    log: pd.DataFrame, case_id: str, activity: str, mandatory: list, standard: list, activity_stats: pd.Series
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """`(schema_usages, partial_schema_usages)`: per activity how many events fill each attribute, its incidence, its local
    attributes and the values it is missing; and the attributes shared by some but not all activities."""
    counts = (
        log.drop(columns=["folded_data", activity], errors="ignore").groupby(log[activity]).count().reindex(activity_stats.index)
    )
    usages = counts.copy()
    usages["incidence"] = usages[case_id]
    non_schema = list(mandatory) + list(standard) + ["incidence"]
    extra = [c for c in counts.columns if c not in non_schema]
    usages["extra_schema"] = [
        {c: int(v) for c, v in row.items() if v != 0} for row in counts[extra].to_dict("records")
    ] if extra else [{} for _ in range(len(usages))]
    usages["local_attributes"] = usages["extra_schema"].apply(lambda d: sorted(d))
    usages["missing_values"] = [
        {c: v - inc for c, v in schema.items() if v - inc != 0} for schema, inc in zip(usages["extra_schema"], usages["incidence"])
    ]
    partial_cols = [c for c in counts.columns if 2 <= (counts[c] != 0).sum() < len(counts)]
    return usages, usages[partial_cols]


# --- views of the log ----------------------------------------------------------------------------------------------------------


def timestamp_components(log: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """How precise the timestamps are and which of their parts are constant (every timestamp column of the log)."""
    return tcu.analyze_timestamp_components(log)


def select_timestamp_component(summary: pd.DataFrame, prefixes: pd.DataFrame, column: str | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The component analysis and the constant prefixes of one timestamp column."""
    pick = lambda frame: frame[frame["Timestamp column"] == column].drop(columns="Timestamp column")  # noqa: E731
    return pick(summary), pick(prefixes)


def event_views(log: pd.DataFrame, found: dict) -> dict:
    """The event tables of the events view: `global` (mandatory and standard attributes) and `inspection` (the same, with the
    attributes that only some activities fill folded into one column). Case-level attributes are left to the case log."""
    columns = [c for c in found["mandatory"] + found["standard"] if c not in found["case_features"]]
    return {"global": log[columns], "inspection": log[columns + ["folded_data"]]}


def local_attribute_view(log: pd.DataFrame, activities: list, found: dict, hide_case_features: bool) -> pd.DataFrame:
    """The events of the selected activities with the attributes common to all their schemas."""
    if not activities:
        return log.iloc[0:0][found["mandatory"]]
    common = set(found["activity_schema"].get(activities[0], []))
    for name in activities[1:]:
        common &= set(found["activity_schema"].get(name, []))
    columns = [c for c in sorted(common) if c != "folded_data" and not (hide_case_features and c in found["case_features"])]
    return log[log[found["mandatory"][1]].isin(activities)][found["mandatory"] + columns]


# --- reading what was recorded -------------------------------------------------------------------------------------------------


def params_at(adapter, state_id: str | None, step_name: str) -> dict | None:
    """The arguments of the last step called `step_name` up to (and including) `state_id`, or in the whole history when
    `state_id` is None. Lets a notebook that is opened again show its widgets as they were left, and lets a reviewer see the widget
    values that produced a result."""
    found = None
    for node_id, node in adapter.get_tree().nodes.items():
        if node.operation.name == step_name:
            found = dict(node.params)
        if state_id is not None and node_id == state_id:
            break
    return found


def step_state_id(adapter, state_id: str | None, step_name: str) -> str | None:
    """The state that the last step called `step_name` produced, up to (and including) `state_id`; None when there is none."""
    found = None
    for node_id, node in adapter.get_tree().nodes.items():
        if node.operation.name == step_name:
            found = node_id
        if state_id is not None and node_id == state_id:
            break
    return found


def _stored_steps(rt) -> list[dict]:
    """The steps of the stored history, oldest first (the history is linear: each state has one step after it)."""
    steps, at, seen = [], rt._root_state_id, set()
    while at not in seen:
        seen.add(at)
        children = rt.storage.load_child_steps(at)
        if not children:
            break
        steps.append(children[-1])
        at = children[-1]["output_state_id"]
    return steps


# Columns that were added to the loaded log after students had saved their work. A stored step whose arguments differ from a new
# call's only by these columns (in a list of columns, say) is the same step, so it must be matched, not recorded again.
_ADDED_COLUMNS = (LIFECYCLE_STATE,)


def _as_recorded_earlier(value):
    """`value` as an earlier version of the notebooks would have passed it: without the `_ADDED_COLUMNS`, which are removed from lists
    and tuples and dropped as dict keys, recursively. Anything else (data frames included) is returned as it is."""
    if isinstance(value, (list, tuple)):
        return type(value)(_as_recorded_earlier(item) for item in value if not (isinstance(item, str) and item in _ADDED_COLUMNS))
    if isinstance(value, dict):
        return {key: _as_recorded_earlier(item) for key, item in value.items() if not (isinstance(key, str) and key in _ADDED_COLUMNS)}
    return value


def analyst_recorder(rt, adapter):
    """`(record, state_of)` for someone doing the analysis: `record(targets, function, *args, name=None, **kwargs)` runs the step and
    stores it, so that an annotation can be attached to what it produced and the analysis can be replayed step by step.

    When a notebook is opened again it runs from the top, and its widgets come back as they were left. A call that is identical to
    the latest stored step of that name is then not stored a second time (it still runs, and what it produced is the stored
    step's), once per step name. The first call that differs, or a second call of the same name, is the analyst's own work: from
    then on every call is stored, so a step repeated on purpose is a new step (the tracker's fingerprint keeps only 200 characters of
    an argument, so a long argument that changed must never be mistaken for a stored one).
    """
    from tracker.runtime import _param_fingerprint

    latest = {step["func_name"]: step for step in _stored_steps(rt)}
    produced: dict = {}
    matched: set = set()  # step names already matched to their stored step: a second call of that name is new work

    def record(targets, function, *args, name=None, **kwargs):
        label = name or function.__name__
        stored = latest.get(label)
        if label not in matched and stored is not None and (
            stored["param_fingerprint"] == _param_fingerprint(list(args), kwargs)
            or stored["param_fingerprint"] == _param_fingerprint(_as_recorded_earlier(list(args)), _as_recorded_earlier(kwargs))
        ):
            matched.add(label)
            result = function(*args, **kwargs)
            for target in targets:
                produced[target] = stored["output_state_id"]
            return result
        matched.update(latest)  # the analyst has moved on: nothing is matched to the stored history from here
        result = rt.trace_step(
            func=function, func_name=label, raw_line=f"{', '.join(targets)} = {label}(...)",
            args=list(args), kwargs=kwargs, targets=list(targets),
        )
        for target in targets:
            produced[target] = rt._current_state_id
        return result

    def state_of(target):
        """The recorded state that produced `target`: what an annotation about it is attached to."""
        return produced.get(target) or (adapter.latest_state_id() if adapter is not None else None) or "analysis"

    return record, state_of


# --- offers ---------------------------------------------------------------------------------------------------------------------
# An application can have several offers. The events of an offer carry its OfferID, except the first one, O_Create Offer, whose
# EventID is the offer's id.


def complete_offer_ids(log: pd.DataFrame) -> pd.Series:
    """The offer each event belongs to: its OfferID, and for O_Create Offer events their EventID; None for the rest."""
    ids = log[OFFER_ID].astype(object).where(log[OFFER_ID].notna(), None)
    create = log[ACTIVITY] == CREATE_OFFER
    return ids.where(~create, log["EventID"].astype(object))


def offers_per_case(log: pd.DataFrame, case_id: str = CASE_ID) -> pd.Series:
    """How many distinct offers each case has."""
    return complete_offer_ids(log).groupby(log[case_id]).nunique()


def offer_distribution(per_case: pd.Series) -> pd.DataFrame:
    """How many cases have one offer, two offers, ..."""
    counts = per_case.value_counts().sort_index()
    return pd.DataFrame({
        "offers per case": counts.index.astype(int),
        "cases": counts.to_numpy(),
        "% of cases": (counts / counts.sum() * 100).round(1).to_numpy(),
    })


# What an analyst writes so that every offer event has an OfferID: the `O_Create Offer` events have none, but their EventID is the id
# of their offer. The result is a copy of the event log with the completed OfferID.
OFFER_ID_CODE = f"""offer_id = event_log['OfferID'].fillna(event_log['EventID'].where(event_log['{ACTIVITY}'] == 'O_Create Offer'))
enriched_event_log = event_log.assign(OfferID=offer_id)"""


def enriched_log_from_code(
    event_log: pd.DataFrame, case_log, code: str | None, names: dict | None = None
) -> pd.DataFrame | None:
    """The `enriched_event_log` that the student's enrichment code defines (run as in `run_enrichment`), or None when it defines
    none. An error in that code propagates."""
    if not code:
        return None
    enriched = run_enrichment(case_log, event_log, code, names).get("enriched_event_log")
    return enriched if isinstance(enriched, pd.DataFrame) else None


def path_attribute_options(log: pd.DataFrame) -> list[str]:
    """The attributes whose values can make up a path (a case) of the map: the case id first, then every other text attribute that
    groups events (more than one value, and not one value per event). The activity and the time do not."""
    options = [CASE_ID]
    for col in log.columns:
        if col in (CASE_ID, ACTIVITY, TIMESTAMP, "folded_data") or pd.api.types.is_datetime64_any_dtype(log[col]):
            continue
        if not (pd.api.types.is_string_dtype(log[col]) or pd.api.types.is_object_dtype(log[col])):
            continue
        distinct = log[col].nunique()
        if 1 < distinct < 0.9 * len(log):
            options.append(col)
    return options


ACTIVITY_COLUMN_LIMIT = 200  # a column with more distinct values than this makes a map with too many nodes to read


def activity_column_options(log: pd.DataFrame) -> list[str]:
    """The columns that can be the activity of a map (its nodes): the activity first, then every other text column with
    2 to `ACTIVITY_COLUMN_LIMIT` distinct values. The case id, the time and the folded data are not offered."""
    options = [ACTIVITY]
    for col in log.columns:
        if col in (ACTIVITY, CASE_ID, TIMESTAMP, "folded_data"):
            continue
        if not (pd.api.types.is_string_dtype(log[col]) or pd.api.types.is_object_dtype(log[col])):
            continue
        if 2 <= log[col].nunique() <= ACTIVITY_COLUMN_LIMIT:
            options.append(col)
    return options


def _events_in_time_frame(log: pd.DataFrame, window) -> pd.DataFrame:
    """The events of the cases (by the case id) that lie completely inside `window`, a [from, to] in the units of `time_frame`. None
    keeps everything."""
    if window is None:
        return log
    frame = time_frame(log, CASE_ID, TIMESTAMP)
    start = frame["start"] + pd.Timedelta(window[0], frame["unit"])
    end = frame["start"] + pd.Timedelta(window[1], frame["unit"])
    return tcu.filter_cases_within_window(log, CASE_ID, TIMESTAMP, start, end)


def time_frame_window(value, stop: int) -> list[int] | None:
    """The time frame that `value` (the slider's value, or a window recorded in an earlier session) stands for: [from, to] as whole
    numbers within 0 to `stop`. None means the whole log: it is the whole range, there is no value, or the value is not two numbers
    (so a damaged history opens with the whole log instead of failing)."""
    try:
        low, high = value
        window = [min(max(int(low), 0), stop), min(max(int(high), 0), stop)]
    except (TypeError, ValueError, OverflowError):  # OverflowError: an infinite recorded value
        return None
    return None if window == [0, stop] else window


def cases_in_time_frame(log: pd.DataFrame, window) -> tuple[int, int]:
    """(cases, events) that lie completely inside `window`."""
    events = _events_in_time_frame(log, window)
    return int(events[CASE_ID].nunique()), len(events)


def to_lcm_log(
    log: pd.DataFrame, case_column: str = CASE_ID, activity_column: str = ACTIVITY, window=None
) -> pd.DataFrame:
    """The case, activity and time columns under the names the map library of `bpm_kit` reads. `case_column` is the attribute that
    makes up a path and `activity_column` the one whose values are the nodes of the map: events without a value for either are left
    out. `window` is a [from, to] in the units of `time_frame`: only the cases that lie completely inside it are kept (None keeps
    everything)."""
    log = _events_in_time_frame(log, window)
    events = pd.DataFrame(
        {
            "case:concept:name": log[case_column],
            "concept:name": log[activity_column],
            "time:timestamp": log[TIMESTAMP],
        }
    )
    return events[events["case:concept:name"].notna() & events["concept:name"].notna()]


def lcm_log_arguments(case_column: str, activity_column: str = ACTIVITY, window=None) -> list:
    """The arguments of `to_lcm_log` after the log, for a recorded step. Only the arguments that differ from their defaults are
    included (a trailing one at its default is left out), so that the recorded step of an earlier version of the notebook stays equal
    to the step recorded now, and a history that is opened again does not record it (and the map) a second time."""
    arguments = [case_column, activity_column, window]
    if window is None:
        arguments.pop()
        if activity_column == ACTIVITY:
            arguments.pop()
    return arguments


# --- saving to the course server, one notebook among several ------------------------------------------------------------------------


# The student package asks once whether a student's analyses may be shared with the course and keeps the answer in the student's home
# folder (launcher/consent.py there). Its launcher already starts the notebooks without a server when the answer is no, but a notebook
# started any other way on the same computer (a development copy, `marimo run` by hand) never sees that. So the notebooks read the
# answer themselves: a recorded "no" holds whatever the environment says.
CONSENT_VERSION = 1  # the version of the consent text an answer was given for; keep it equal to CONSENT_VERSION in launcher/consent.py


def sharing_allowed(home=None) -> bool:
    """Whether this student has agreed to share their analyses with the course server.

    No answer file means the notebook does not run from the student package (a hosted or a development copy): there is no answer to
    respect, so nothing is held back. A file that is unreadable, was given for another consent text, or says anything but "accepted"
    counts as no."""
    path = (Path(home) if home is not None else Path.home()) / ".hs-marimo26" / "consent.json"
    if not path.exists():
        return True
    try:
        record = json.loads(path.read_text(encoding="utf8"))
        return record["version"] == CONSENT_VERSION and record["choice"] == "accepted"
    except (OSError, ValueError, KeyError, TypeError):
        return False


def course_server(url: str, home=None) -> str:
    """`url`, unless the student said no to sharing: then "" (no server, the work stays on this computer)."""
    return url if url and sharing_allowed(home) else ""


def sync_url(base: str, notebook: str) -> str:
    """The address a notebook saves to: the server's, with the notebook's own id in the path (the sync client adds /v1/provenance)."""
    return f"{base.rstrip('/')}/n/{notebook}"


def session_folder(key: str, notebook: str) -> Path:
    """Where one student's work in one notebook lives on this computer: a folder per key and notebook, so two notebooks that share
    a key (and a computer) never write into each other's provenance.

    The student package names its data folder in `PMPROV_DIR`; the work is kept beside it (`synced/`), where it stays between
    sessions, so a notebook opened without a connection still has it. Elsewhere (a hosted notebook) it is in the temporary folder."""
    name = hashlib.sha256(f"{key}/{notebook}".encode()).hexdigest()[:16]
    package_data = os.environ.get("PMPROV_DIR")
    if package_data:
        return Path(package_data).with_name("synced") / name
    return Path(tempfile.gettempdir()) / "bpm-provenance" / name


def write_notebook_info(folder, notebook: str, source, version: str | None = None) -> Path:
    """Say in `notebook.json`, inside the provenance folder that gets saved, which notebook this is and a hash of its file, so that
    the course server can tell which version of the notebook made each saved revision. A notebook whose file cannot be read (a hosted
    one) still says which notebook it is."""
    try:
        digest = hashlib.sha256(Path(source).read_bytes()).hexdigest()
    except Exception:
        digest = None
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "notebook.json"
    target.write_text(json.dumps({"notebook": notebook, "sha256": digest, "version": version}), encoding="utf-8")
    return target


def normalise_log(log: pd.DataFrame) -> pd.DataFrame:
    """Any event log with the column names of the course notebooks: colons in names become underscores (the marimo explorer breaks
    on them), and an `activity_extended` column ("<activity>_<lifecycle>") is added when the log has a lifecycle and no such column
    yet. The `lifecycle_state` column is added too (see `add_lifecycle_state`)."""
    out = log.rename(columns=lambda name: str(name).replace(":", "_"))
    if ACTIVITY_EXTENDED not in out.columns and {ACTIVITY, LIFECYCLE} <= set(out.columns):
        out[ACTIVITY_EXTENDED] = out[ACTIVITY].astype("string") + "_" + out[LIFECYCLE].astype("string")
    return add_lifecycle_state(out)


def read_log(path) -> pd.DataFrame:
    """An event log in the format it came in: `.csv` (columns with a time or date in their name are read as timestamps), `.xes` (one
    row per event, trace attributes as `case:` columns, see `xes_reader`) or `.parquet`."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".xes":
        from xes_reader import read_xes

        return read_xes(str(path))
    if suffix == ".csv":
        log = pd.read_csv(path)
        for col in log.columns:
            if not (pd.api.types.is_string_dtype(log[col]) or pd.api.types.is_object_dtype(log[col])):
                continue
            if "time" not in str(col).lower() and "date" not in str(col).lower():
                continue
            parsed = pd.to_datetime(log[col], errors="coerce")
            if parsed.notna().mean() >= 0.9:  # a column that really holds times, not one that only has "time" in its name
                log[col] = parsed
        return log
    raise ValueError(f"cannot read {path.name}: a log is a .csv, .xes or .parquet file")


def guess_mandatory(columns: list, timestamp_columns: list) -> dict:
    """The case id, activity and completion time columns of a log, found by their names (the course notebooks' own names first, then
    names such as `Case ID`, `Activity` and `Complete Timestamp`); the first two columns and the last timestamp when nothing matches."""
    columns, timestamps = list(columns), list(timestamp_columns)

    def first(predicate):
        return next((c for c in columns if predicate(str(c).lower())), None)

    case_id = (
        CASE_ID if CASE_ID in columns
        else first(lambda c: "case" in c and ("id" in c or "name" in c))
        or columns[0]
    )
    activity = (
        ACTIVITY if ACTIVITY in columns
        else first(lambda c: "activity" in c or c.endswith("concept_name") and "case" not in c)
        or next((c for c in columns if c != case_id), columns[0])
    )
    completion = (
        TIMESTAMP if TIMESTAMP in timestamps
        else next((c for c in timestamps if "complete" in str(c).lower()), None)
        or (timestamps[-1] if timestamps else None)
    )
    return {"case_id": case_id, "activity": activity, "completion_time": completion}


# --- the version and "Stop the app" -------------------------------------------------------------------------------------------------


def notebooks_version(folder) -> str:
    """The version of the notebooks: the `version` in the `version.json` that the runtime keeps beside the `notebooks/` folder. A
    copy that is not run from the student package has no such file (or an unreadable one) and is a "development copy"."""
    try:
        return str(json.loads((Path(folder).parent / "version.json").read_text(encoding="utf8"))["version"])
    except (OSError, ValueError, KeyError, TypeError):
        return "development copy"


def server_pid() -> int:
    """The process of the marimo server that runs this notebook. `marimo run <folder>` (what the launcher does) starts each notebook in
    an "app host" process, a child of the server. A notebook of `marimo edit` runs in a `multiprocessing` child of the server. With
    `marimo run <file>` the notebook is a thread of the server itself."""
    spec = getattr(sys.modules.get("__main__"), "__spec__", None)
    if str(getattr(spec, "name", "") or "").startswith("marimo._session.app_host"):
        return os.getppid()
    parent = multiprocessing.parent_process()
    if parent is not None:
        return parent.pid
    return os.getpid()


def stop_app(delay: float = 1.0, grace: float = 3.0) -> None:
    """Ends the marimo server (and with it every open notebook) after `delay` seconds, so that the click that asked for it still
    gets its answer. When the server is this very process, it is ended `grace` seconds after the request to shut down if it has not
    ended by then: on macOS SIGTERM asks the server to shut down, and it may wait for the open page (on Windows the kill ends it)."""

    def stop() -> None:
        pid = server_pid()
        os.kill(pid, signal.SIGTERM)
        if pid == os.getpid():
            time.sleep(grace)
            os._exit(0)

    threading.Timer(delay, stop).start()


def app_bar(mo, folder, stop_button):
    """One row at the right of the page: the version of the notebooks in small grey text, and the button that stops the app."""
    version = mo.md(f'<span style="color:#6b7280;font-size:0.8em">Version {notebooks_version(folder)}</span>')
    return mo.hstack([version, stop_button], justify="end", align="center")


def stop_confirmation(mo, confirm_button):
    """What the page shows after "Stop the app" is pressed: a warning and `confirm_button`, the button that really stops it (made by
    the notebook, see there)."""
    return mo.callout(
        mo.vstack([
            mo.md(
                "Stop the app? All open notebooks stop; work that was saved stays saved. Afterwards this page no longer responds: "
                "close its tab and the window that opened when you started."
            ),
            confirm_button,
        ]),
        kind="warn",
    )
