import sys
from pathlib import Path

import marimo as mo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notebooks" / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notebooks"))
import bpm_kit as kit  # noqa: E402

NAMES = ["a", "b", "c", "d"]
NOTIONS = {"Case ID": "application"}


def _controls(settings=None, fold_rows=None, fold_values=None):
    return kit.map_controls(mo, NAMES, settings, NOTIONS, fold_rows, fold_values)


def test_no_fold_rows_by_default():
    controls = _controls()
    assert len(controls["folds"].value) == 0
    assert kit.settings_from(controls.value, NAMES)["folds"] == {}


def test_settings_with_two_folds_show_two_rows():
    controls = _controls({"folds": {"x": ["a", "b"], "y": ["c"]}})
    assert len(controls["folds"].value) == 2


def test_fold_rows_asks_for_more_rows():
    assert len(_controls(fold_rows=3)["folds"].value) == 3
    assert len(_controls({"folds": {"x": ["a"]}}, fold_rows=3)["folds"].value) == 3
    assert len(_controls({"folds": {"x": ["a"], "y": ["b"]}}, fold_rows=1)["folds"].value) == 2


def test_a_recorded_history_with_three_folds_round_trips():
    folds = {"x": ["a"], "y": ["b"], "z": ["c", "d"]}
    controls = _controls({"activities": ["a", "b", "c"], "folds": folds})
    assert len(controls["folds"].value) == 3
    assert kit.settings_from(controls.value, NAMES)["folds"] == folds


def test_layout_without_folds_has_no_accordion_and_with_folds_holds_the_button():
    controls = _controls(fold_rows=1)
    button = mo.ui.button(label="Add fold")
    plain = kit.controls_layout(mo, controls, mo.md(""), mo.ui.button(label="r"), mo.md(""), False, show_folds=False)
    assert "Activity folding" not in plain.text
    full = kit.controls_layout(mo, controls, mo.md(""), mo.ui.button(label="r"), mo.md(""), False, add_fold=button)
    assert "Activity folding" in full.text
    empty = kit.controls_layout(mo, _controls(), mo.md(""), mo.ui.button(label="r"), mo.md(""), False, add_fold=button)
    assert "Activity folding" in empty.text


def _rebuild(kept, column, adds, draft=None):
    return kit.build_map_controls(mo, NAMES, draft, NOTIONS, kept, column, adds)


def _remember(kept, controls, column):
    kept.update(kit.kept_controls_of(controls.value))
    kept.update(kit.kept_column_controls_of(controls.value, column))


def test_adding_a_fold_keeps_what_was_typed_and_selected():
    kept = {}
    controls = _rebuild(kept, "col", 0)
    assert len(controls["folds"].value) == 0
    # the analyst narrows the activities, then adds a row
    controls = kit.map_controls(mo, NAMES, {"activities": ["a", "b"]}, NOTIONS, 1, [("rel", ["a"])])
    _remember(kept, controls, "col")
    controls = _rebuild(kept, "col", 1)
    assert len(controls["folds"].value) == 2
    assert controls["activities"].value == ["a", "b"]
    assert controls["folds"].value[0] == {"name": "rel", "activities": ["a"]}
    assert controls["folds"].value[1] == {"name": "", "activities": []}
    _remember(kept, controls, "col")
    controls = _rebuild(kept, "col", 2)  # a second click
    assert len(controls["folds"].value) == 3
    _remember(kept, controls, "col")
    controls = _rebuild(kept, "col", 2)  # a rebuild that is not a click keeps three
    assert len(controls["folds"].value) == 3


def test_a_change_of_the_activity_column_drops_the_selection_and_the_folds():
    kept = {}
    controls = kit.map_controls(mo, NAMES, {"activities": ["a"], "map_type": "sequence_based", "allow_loops": True}, NOTIONS, 2, [("rel", ["a"]), ("", [])])
    _remember(kept, controls, "col")
    other = _rebuild(kept, "other", 0, draft=kit.normalise_settings({"activities": ["b", "c"]}))
    assert other["activities"].value == ["b", "c"]
    assert len(other["folds"].value) == 0
    assert other.value["map_type"] == "sequence_based" and other.value["allow_loops"] is True


def test_recorded_folds_of_the_draft_appear_on_the_first_build():
    draft = kit.normalise_settings({"folds": {"x": ["a"], "y": ["b"], "z": ["c"]}})
    controls = _rebuild({}, "col", 0, draft=draft)
    assert len(controls["folds"].value) == 3
