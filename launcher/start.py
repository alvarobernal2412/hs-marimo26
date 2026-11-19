"""Starts the course notebooks: update, then `marimo run` on the notebooks folder, then the browser. Standard library only."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import update  # noqa: E402

PREFERRED_PORT = 2718


def state_dir() -> Path:
    """Where a student's own files live. Never inside the bundle, so updates and new downloads leave them alone."""
    return Path.home() / ".hs-marimo26"


def free_port(preferred: int = PREFERRED_PORT) -> int:
    for candidate in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", candidate))
            except OSError:
                continue
            return s.getsockname()[1]
    raise OSError("no free port")


def build_command(root: Path, port: int, python: str | None = None) -> list[str]:
    return [python or sys.executable, "-m", "marimo", "run", str(Path(root) / "notebooks"), "--headless", "--port", str(port)]


def remember_port(state: Path, port: int) -> None:
    Path(state).mkdir(parents=True, exist_ok=True)
    (Path(state) / "running.port").write_text(str(port), encoding="utf8")


def running_port(state: Path) -> int | None:
    """The port of a server this launcher already started, if something still listens there."""
    try:
        port = int((Path(state) / "running.port").read_text(encoding="utf8").strip())
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return port
    except (OSError, ValueError):
        return None


def wait_until_listening(port: int, seconds: int = 120) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def main(root: Path) -> int:
    root, state = Path(root), state_dir()
    already = running_port(state)
    if already:
        print(f"The notebooks are already running; opening http://localhost:{already}")
        webbrowser.open(f"http://localhost:{already}")
        return 0
    update.main(root)
    port = free_port()
    remember_port(state, port)
    env = {**os.environ, "PMPROV_DIR": str(state / "provenance")}
    print(f"Starting the notebooks at http://localhost:{port} (close this window to stop them)")
    process = subprocess.Popen(build_command(root, port), env=env)
    if wait_until_listening(port):
        webbrowser.open(f"http://localhost:{port}")
    try:
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        return 0
    finally:
        try:
            (state / "running.port").unlink()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]))
