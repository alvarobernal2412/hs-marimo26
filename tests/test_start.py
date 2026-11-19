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
