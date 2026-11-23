import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "launcher"))
import start  # noqa: E402


def test_free_port_skips_busy_port():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        assert start.free_port(port) != port


def test_a_busy_port_falls_back_to_the_next_fixed_one_so_the_browser_keeps_what_it_remembered():
    # the browser remembers the student's key per address: a port picked at random would forget it on every start
    held = []
    try:
        for port in start.PORTS[:2]:
            s = socket.socket()
            try:
                s.bind(("127.0.0.1", port))
                s.listen()
                held.append(s)
            except OSError:
                s.close()  # something else already has it, which is the same for this test
        assert start.free_port() == start.PORTS[2]
    finally:
        for s in held:
            s.close()
    assert start.PORTS[0] == 2718 and len(start.PORTS) >= 5


def test_free_port_returns_preferred_when_free():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert start.free_port(port) == port


def test_command_keeps_paths_with_spaces_and_non_ascii_as_single_arguments(tmp_path):
    root = tmp_path / "Ünï cödé dir"
    command = start.build_command(root, 2718, python="py thon")
    assert command[0] == "py thon"
    assert str(root / "notebooks") in command
    assert command[command.index("--port") + 1] == "2718"
    assert "--headless" in command
    assert command[1] == "-s"  # the bundle never reads packages from the student's user site
    assert command[command.index("marimo") + 1:command.index("run")] == ["-l", "error"]  # no warning lines in the student's window


def test_running_instance_detected_from_state_file(tmp_path):
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        start.remember_port(tmp_path, port)
        assert start.running_port(tmp_path) == port
    assert start.running_port(tmp_path) is None  # nothing listens any more


def test_no_state_file_means_not_running(tmp_path):
    assert start.running_port(tmp_path) is None


# ---- consent ---------------------------------------------------------------------------------------------------------------
import consent  # noqa: E402
import pytest  # noqa: E402


def _must_not_ask(state):
    raise AssertionError("the consent page must not be shown")


def test_resolve_consent_uses_saved_answer_without_asking(tmp_path):
    consent.save(tmp_path, "accepted")
    assert start.resolve_consent(tmp_path, force=False, ask=_must_not_ask) == "accepted"


def test_resolve_consent_asks_when_unanswered(tmp_path):
    assert start.resolve_consent(tmp_path, force=False, ask=lambda state: "declined") == "declined"


def test_resolve_consent_force_asks_again(tmp_path):
    consent.save(tmp_path, "accepted")
    assert start.resolve_consent(tmp_path, force=True, ask=lambda state: "declined") == "declined"


def test_resolve_consent_never_blocks_the_start_when_the_page_fails(tmp_path):
    def broken(state):
        raise OSError("cannot open a port")

    assert start.resolve_consent(tmp_path, force=False, ask=broken) == "undecided"


def test_the_start_fetches_the_course_files_and_never_stops_when_that_fails(tmp_path):
    asked = []
    assert start.fetch_course_files(tmp_path, tmp_path / "state", ensure=lambda root, state: asked.append((root, state)) or "downloaded") == "downloaded"
    assert asked == [(tmp_path, tmp_path / "state")]

    def broken(root, state):
        raise OSError("cannot open a port")

    assert start.fetch_course_files(tmp_path, tmp_path / "state", ensure=broken) == "skipped"


@pytest.mark.parametrize("choice", ["accepted", "declined", "undecided"])
@pytest.mark.parametrize("preset", [None, "https://example.org/sync"])
def test_marimo_env_blanks_sync_url_unless_accepted(tmp_path, choice, preset):
    base = {"PATH": "x"} if preset is None else {"PATH": "x", "PMPROV_SYNC_URL": preset}
    env = start.marimo_env(base, tmp_path, choice)
    assert env["PMPROV_DIR"] == str(tmp_path / "provenance")
    assert env["PYTHONNOUSERSITE"] == "1"
    assert env["PATH"] == "x"
    if choice == "accepted":
        assert env.get("PMPROV_SYNC_URL") == preset  # untouched: unset stays unset, a preset stays
    else:
        assert env["PMPROV_SYNC_URL"] == ""
    assert base.get("PMPROV_SYNC_URL") == preset  # the caller's environment is not modified


def test_main_does_not_ask_for_consent_when_the_server_already_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(start, "running_port", lambda state: 2718)
    monkeypatch.setattr(start.webbrowser, "open", lambda url: True)
    monkeypatch.setattr(consent, "ask", _must_not_ask)
    assert start.main(tmp_path) == 0


def test_main_refuses_to_change_the_answer_while_the_notebooks_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["start.py", str(tmp_path), "--consent"])
    monkeypatch.setattr(start, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(start, "running_port", lambda state: 2718)

    def must_not_open(url):
        raise AssertionError("no browser must open")

    monkeypatch.setattr(start.webbrowser, "open", must_not_open)
    monkeypatch.setattr(consent, "ask", _must_not_ask)
    assert start.main(tmp_path) == 1
    assert f"Close the {start.window_name()} first, then double-click Change-my-answer again." in capsys.readouterr().out


def test_the_window_to_close_is_named_as_each_system_shows_it():
    assert start.window_name("win32") == "black window"
    assert start.window_name("darwin") == "Terminal window"  # a Mac's Terminal is not black


@pytest.mark.skipif(sys.platform != "win32", reason="job objects are a Windows feature")
def test_the_server_dies_with_the_launcher_so_nothing_stays_running_in_the_background():
    import ctypes
    import subprocess

    server = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    try:
        job = start.tie_to_this_process(server)
        assert job and server.poll() is None
        ctypes.windll.kernel32.CloseHandle(job)  # what Windows does when the launcher ends, however it ends
        assert server.wait(timeout=15) is not None
    finally:
        server.kill()


def test_tying_the_server_to_the_launcher_does_nothing_off_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert start.tie_to_this_process(object()) is None


def test_start_refuses_remove_data_while_running(tmp_path, monkeypatch, capsys):
    import removal

    monkeypatch.setattr(sys, "argv", ["start.py", str(tmp_path), "--remove-data"])
    monkeypatch.setattr(start, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(start, "running_port", lambda state: 2718)
    monkeypatch.setattr(start.webbrowser, "open", lambda url: (_ for _ in ()).throw(AssertionError("no browser must open")))

    def must_not_ask(*args, **kwargs):
        raise AssertionError("the removal page must not be shown")

    monkeypatch.setattr(removal, "ask", must_not_ask)
    assert start.main(tmp_path) == 1
    assert f"Close the {start.window_name()} first, then double-click Remove-my-data again." in capsys.readouterr().out
