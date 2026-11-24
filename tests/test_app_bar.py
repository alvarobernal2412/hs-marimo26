import signal
import sys
import threading
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notebooks" / "lib"))
import initial_analysis_kit as ak  # noqa: E402


def _folder(tmp_path):
    folder = tmp_path / "notebooks"
    folder.mkdir()
    return folder


def test_the_version_is_read_from_beside_the_notebooks(tmp_path):
    (tmp_path / "version.json").write_text('{"version": "1.3.0"}', encoding="utf8")
    assert ak.notebooks_version(_folder(tmp_path)) == "1.3.0"


def test_a_missing_or_broken_version_file_is_a_development_copy(tmp_path):
    folder = _folder(tmp_path)
    assert ak.notebooks_version(folder) == "development copy"
    (tmp_path / "version.json").write_text("{not json", encoding="utf8")
    assert ak.notebooks_version(folder) == "development copy"


def test_stop_app_ends_the_server_after_the_delay(monkeypatch):
    calls, done = [], threading.Event()
    monkeypatch.setattr(ak.os, "kill", lambda pid, sig: (calls.append((pid, sig)), done.set()))
    ak.stop_app(delay=0)
    assert done.wait(5)
    assert calls == [(ak.server_pid(), signal.SIGTERM)]


def test_server_pid_in_an_app_host_is_the_parent(monkeypatch):
    main = types.SimpleNamespace(__spec__=types.SimpleNamespace(name="marimo._session.app_host.main"))
    monkeypatch.setitem(sys.modules, "__main__", main)
    monkeypatch.setattr(ak.os, "getppid", lambda: 4242)
    assert ak.server_pid() == 4242


def test_server_pid_in_a_multiprocessing_child_is_the_parent_process(monkeypatch):
    monkeypatch.setitem(sys.modules, "__main__", types.SimpleNamespace(__spec__=None))
    monkeypatch.setattr(ak.multiprocessing, "parent_process", lambda: types.SimpleNamespace(pid=777))
    assert ak.server_pid() == 777


def test_server_pid_otherwise_is_this_process(monkeypatch):
    monkeypatch.setitem(sys.modules, "__main__", types.SimpleNamespace(__spec__=None))
    monkeypatch.setattr(ak.multiprocessing, "parent_process", lambda: None)
    assert ak.server_pid() == ak.os.getpid()


import ast  # noqa: E402

import pytest  # noqa: E402

NOTEBOOKS = [
    "00_lecture-initial-analysis.py", "01_assignment-initial-analysis.py", "02_lecture-process-map.py", "03_assignment-process-map.py",
]


@pytest.mark.parametrize("notebook", NOTEBOOKS)
def test_the_confirm_button_is_a_variable_of_the_notebook(notebook):
    """marimo answers the click of a button only when the button is a global variable of the notebook."""
    path = Path(__file__).resolve().parents[1] / "notebooks" / notebook
    cells = [n for n in ast.parse(path.read_text(encoding="utf8")).body if isinstance(n, ast.FunctionDef)]
    defining = []
    for cell in cells:
        for node in ast.walk(cell):
            if (
                isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "confirm_stop" for t in node.targets)
                and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "mo.ui.button"
            ):
                returned = [n for n in cell.body if isinstance(n, ast.Return)]
                assert returned and "confirm_stop" in ast.unparse(returned[0]), f"{notebook}: confirm_stop is not returned"
                defining.append(cell)
    assert len(defining) == 1, f"{notebook}: no cell makes confirm_stop with mo.ui.button"
    assert "stop_confirmation(mo, confirm_stop)" in ast.unparse(defining[0])
