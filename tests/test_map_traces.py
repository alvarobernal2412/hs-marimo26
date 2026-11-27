"""`kit.draw_map` passes the layout of the map library through and returns its traces (Task 9)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notebooks" / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notebooks"))
import bpm_kit as kit  # noqa: E402

lcm = pytest.importorskip("lcm")


def _toy_log():
    """The toy log of the slides: {A, AKLZ, AKLZ, ALKZ}."""
    traces = {"c1": "AKLZ", "c2": "ALKZ", "c3": "A", "c4": "AKLZ"}
    rows = [
        {kit.CASE_ID: case, kit.ACTIVITY: activity, kit.TIMESTAMP: pd.Timestamp("2024-01-01") + pd.Timedelta(days=i)}
        for case, sequence in traces.items()
        for i, activity in enumerate(sequence)
    ]
    return pd.DataFrame(rows)


def _draw(log, layout="auto", **kwargs):
    return kit.draw_map(log, None, "sequence_based", True, True, {}, "application", layout=layout, **kwargs)


def test_draw_map_returns_traces():
    figure, meta = _draw(_toy_log(), layout="traces")
    assert [t["name"] for t in kit.traces_of(figure)] == ["A → K → L → Z", "A → L → K → Z", "A"]
    assert [t["cases"] for t in kit.traces_of(figure)] == [2, 1, 1]
    assert meta["traces_truncated"] is False and meta["trace_count"] == 3
    assert "traces" not in meta  # the figure carries them; the metadata is recorded too
    assert meta["settings"]["layout"] == "traces"


def test_default_layout_keeps_the_recorded_call(monkeypatch):
    """A map drawn with the default layout calls the library and records its settings exactly as before the layout existed."""
    calls = []
    service = kit._service(_toy_log(), "application")[0]
    real = type(service).generate

    def generate(self, **kwargs):
        calls.append(kwargs)
        return real(self, **kwargs)

    monkeypatch.setattr(type(service), "generate", generate)
    log = _toy_log()
    _, meta = kit.draw_map(log, None, "set_based", True, True, {}, "application")
    assert "layout" not in calls[-1] and calls[-1]["trace_limit"] == kit.MAP_TRACE_LIMIT
    assert set(meta["settings"]) == {"activities", "map_type", "allow_loops", "show_empty", "folds", "case_notion"}
    assert "trace_count" in meta and "traces_truncated" in meta
    assert kit.DEFAULT_SETTINGS == {
        "activities": None, "map_type": "set_based", "allow_loops": True, "show_empty": True, "folds": {},
        "case_notion": "application",
    }


def test_a_traces_map_is_laid_out_again_for_its_size():
    """The positions depend on the size of the figure: after its height and margins are set, the kit places the nodes again."""
    log = _toy_log()
    figure, _ = _draw(log, layout="traces", height=620, room=(100, 140, 110))

    service = lcm.get_service(log)
    by_hand, _ = service.generate(activities=["A", "K", "L", "Z"], map_type="sequence_based", layout="traces")
    by_hand.update_layout(height=620, margin=dict(l=110, r=10, t=100, b=140))
    before = tuple(by_hand.data[0].node.y)
    lcm.relayout(by_hand)
    assert tuple(figure.data[0].node.y) == pytest.approx(tuple(by_hand.data[0].node.y))
    assert tuple(figure.data[0].node.y) != pytest.approx(before)
