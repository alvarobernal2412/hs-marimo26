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
