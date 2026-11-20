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
import consent  # noqa: E402
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
    return [python or sys.executable, "-s", "-m", "marimo", "run", str(Path(root) / "notebooks"), "--headless", "--port", str(port)]


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


def resolve_consent(state: Path, force: bool, ask=consent.ask) -> str:
    """The student's answer: the saved one, or (first start, a changed consent text, or `--consent`) the one the page collects."""
    saved = None if force else consent.load(state)
    if saved is not None:
        return saved
    try:
        return ask(state)
    except Exception:  # like the updater: whatever goes wrong, the student can still start (local-only, asked again next time)
        return "undecided"


def marimo_env(base: dict, state: Path, choice: str) -> dict:
    """The environment of the notebooks server. Unless the student accepted, the sync URL is blank: the notebooks then work
    without the course server and keep everything on this computer."""
    env = {**base, "PMPROV_DIR": str(Path(state) / "provenance"), "PYTHONNOUSERSITE": "1"}  # only the bundle's own packages
    if choice != "accepted":
        env["PMPROV_SYNC_URL"] = ""
    return env


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
    if already and "--consent" in sys.argv[2:]:
        # the running notebooks keep the answer they started with: it can only change on a fresh start
        print("Close the black window first, then double-click Change-my-answer again.")
        return 1
    if already:
        print(f"The notebooks are already running; opening http://localhost:{already}")
        webbrowser.open(f"http://localhost:{already}")
        return 0
    update.main(root)
    choice = resolve_consent(state, force="--consent" in sys.argv[2:])
    port = free_port()
    remember_port(state, port)
    env = marimo_env(os.environ, state, choice)
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
