"""Where the nodes of the process map were dragged to comes back when the notebook is opened again."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def adapter_with(*steps):
    nodes = {state: SimpleNamespace(operation=SimpleNamespace(name=name), params=params) for state, name, params in steps}
    return SimpleNamespace(get_tree=lambda: SimpleNamespace(nodes=nodes))


def test_a_notebook_opened_again_shows_the_map_as_it_was_left_and_a_map_drawn_again_starts_as_drawn():
    sys.path.insert(0, str(ROOT / "notebooks"))
    kit = pytest.importorskip("bpm_kit")
    adapter = adapter_with(
        ("s1", "draw_map", {}), ("s2", "arrange_map", {"positions": "first"}), ("s3", "visualize_chart", {}),
        ("s4", "arrange_map", {"positions": "later"}),
    )
    assert kit.last_arrangement(adapter, "s1") == "later"
    again = adapter_with(("s1", "draw_map", {}), ("s2", "arrange_map", {"positions": "first"}), ("s3", "draw_map", {}))
    assert kit.last_arrangement(again, "s3") is None and kit.last_arrangement(again, "s1") is None
    assert kit.last_arrangement(adapter_with(("s1", "draw_map", {})), "s1") is None
