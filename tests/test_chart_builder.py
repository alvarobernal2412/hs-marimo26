import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notebooks" / "lib"))
import display_util as du  # noqa: E402


def test_enable_chart_builder_makes_the_table_plugin_see_edit_mode(monkeypatch):
    from marimo._plugins.ui._impl import table as table_plugin

    monkeypatch.setattr(table_plugin, "get_mode", lambda: "run")  # restored by monkeypatch after the test
    assert du.enable_chart_builder() is True
    assert table_plugin.get_mode() == "edit"


def test_enable_chart_builder_never_raises_when_marimo_changes(monkeypatch):
    from marimo._plugins.ui._impl import table as table_plugin

    monkeypatch.delattr(table_plugin, "get_mode")  # a marimo without that name: restored after the test
    assert du.enable_chart_builder() is False
    assert not hasattr(table_plugin, "get_mode")  # and nothing was added in its place
