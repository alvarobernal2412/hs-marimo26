"""A recorded map stays small: the work a student saves to the course server leaves out every recorded value over 500 KB
(marimo-pmprov's `zip_provenance`, which Sync uses), so a map that stores too many traces would be lost from it."""
import pickle
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
LIMIT = 150_000  # well under the 500 KB of zip_provenance
DHANA = ROOT / "notebooks" / ak.DHANA


def test_a_map_with_hundreds_of_traces_stores_at_most_the_limit():
    """The Sepsis log, set-based, all 16 activities: hundreds of distinct traces."""
    log = ak.load_log(ROOT / "notebooks" / "data" / "SepsisCases2020EventLog.xes")
    figure, meta = kit.draw_map(ak.to_lcm_log(log, ak.CASE_ID), None, "set_based", True, True, {}, "application", 900)
    assert meta["traces_truncated"] is True
    assert meta["trace_count"] == len(kit.traces_of(figure)) <= kit.MAP_TRACE_LIMIT == 50
    assert "traces" not in meta
    assert len(figure.to_json().encode()) < LIMIT
    assert len(pickle.dumps(meta)) < LIMIT


@pytest.mark.skipif(not DHANA.is_file(), reason="the Dhana log is not public and is not here")
def test_a_default_map_of_03_is_recorded_small(tmp_path):
    """A default map of 03 (the 5 most frequent activities of the Dhana log, set-based), recorded with the real recorder: the stored
    figure and metadata of the step are each well under the limit, and the zip of the work leaves nothing out."""
    from provenance_widget.pmprov_adapter import PmprovAdapter
    from provenance_widget.portable import zip_provenance
    from tracker import init_marimo

    warnings.filterwarnings("ignore", message=r"init_marimo\(\) was called but patch_marimo_ast_compile")
    folder = tmp_path / "provenance"
    (folder / "artifacts").mkdir(parents=True)
    rt = init_marimo(
        history_name="size", branch_name="main", db_path=str(folder / "provenance.db"),
        artifact_dir=str(folder / "artifacts"), fresh=True,
    )
    record, _ = ak.analyst_recorder(rt, PmprovAdapter(rt))
    log = ak.load_event_log(DHANA)
    lcm_log = ak.to_lcm_log(log, ak.CASE_ID)
    activities = sorted(log[ak.ACTIVITY].value_counts().index[:5])
    record(
        ["map_figure", "map_meta"], kit.draw_map,
        lcm_log, activities, "set_based", True, True, {}, "application", 900, room=(100, 140, 110),
    )
    rt.storage._executor.submit(lambda: None).result()  # let queued writes land
    # the step's outputs as pmprov stores them: the figure as Plotly JSON, the metadata pickled (the input, the log, is a parquet
    # file; the database cannot be read for the names while the tracker holds it open)
    stored = list((folder / "artifacts").iterdir())
    sizes = {kind: [p.stat().st_size for p in stored if p.name.endswith(suffix)] for kind, suffix in (("map_figure", ".plotly.json"), ("map_meta", ".pkl"))}
    assert all(len(found) == 1 for found in sizes.values()), sizes
    assert all(found[0] < LIMIT for found in sizes.values()), sizes
    _, left_out = zip_provenance(folder)
    assert not [name for name, _ in left_out if name.endswith((".plotly.json", ".pkl"))], left_out
