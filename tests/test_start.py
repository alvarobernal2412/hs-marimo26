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
