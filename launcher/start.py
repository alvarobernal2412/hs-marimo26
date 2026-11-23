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
import coursefiles  # noqa: E402
import notice  # noqa: E402
import removal  # noqa: E402
import update  # noqa: E402

PREFERRED_PORT = 2718
# tried in this order before any free port: the browser remembers the student's key per address, so the address should not change
PORTS = tuple(range(PREFERRED_PORT, PREFERRED_PORT + 5))


def state_dir() -> Path:
    """Where a student's own files live. Never inside the bundle, so updates and new downloads leave them alone."""
    return Path.home() / ".hs-marimo26"


def free_port(preferred: int = PREFERRED_PORT) -> int:
    for candidate in (preferred, *(p for p in PORTS if p != preferred), 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", candidate))
            except OSError:
                continue
            return s.getsockname()[1]
    raise OSError("no free port")


def build_command(root: Path, port: int, python: str | None = None) -> list[str]:
    # "-l error": marimo warns about the title each notebook sets in its header (it reads the title, and ignores the header as
    # configuration), once per opened notebook; a student would take those lines in the window for a problem
    return [python or sys.executable, "-s", "-m", "marimo", "-l", "error", "run", str(Path(root) / "notebooks"), "--headless", "--port", str(port)]


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


def fetch_course_files(root: Path, state: Path, ensure=coursefiles.ensure) -> str:
    """The event log that is not public: downloaded with the course code when this computer does not have it (see coursefiles.py).
    Whatever goes wrong, the student still starts; the notebooks that need the log say what to do."""
    try:
        return ensure(root, state)
    except Exception:
        return "skipped"


def tell_about_new_package(result: str, show=notice.show) -> None:
    """When the update found a release that needs a new package, say so in the browser before the notebooks open. Whatever goes
    wrong with the page, the student still starts."""
    if result != "needs-package":
        return
    try:
        show()
    except Exception:
        pass


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


def tie_to_this_process(process):
    """Windows: makes the notebooks server die with this launcher, whatever ends the launcher (a crash, "End task"), so no server is
    left running in the background. Returns the job handle, which must stay alive as long as the launcher does. Best effort: None
    when it is not possible, and on other systems (there, closing the window ends both)."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]

    class Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64), ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD), ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class Extended(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", IoCounters), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = Extended()
    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    ok = kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))  # 9 = JobObjectExtendedLimitInformation
    ok = ok and kernel32.AssignProcessToJobObject(job, int(process._handle))
    return job if ok else None


def window_name(platform: str = sys.platform) -> str:
    """What a student sees the launcher's window as: black on Windows, the Terminal on a Mac."""
    return "black window" if platform == "win32" else "Terminal window"


def sync_server(environ=os.environ) -> str:
    """The course server the notebooks talk to: `PMPROV_SYNC_URL` when set (and not empty), else the course's own."""
    return environ.get("PMPROV_SYNC_URL") or coursefiles.SERVER


def main(root: Path) -> int:
    root, state = Path(root), state_dir()
    already = running_port(state)
    if already and "--remove-data" in sys.argv[2:]:
        # the running notebooks hold their work open: removing it has to happen before they start
        print(f"Close the {window_name()} first, then double-click Remove-my-data again.")
        return 1
    if already and "--consent" in sys.argv[2:]:
        # the running notebooks keep the answer they started with: it can only change on a fresh start
        print(f"Close the {window_name()} first, then double-click Change-my-answer again.")
        return 1
    if already:
        print(f"The notebooks are already running; opening http://localhost:{already}")
        webbrowser.open(f"http://localhost:{already}")
        return 0
    tell_about_new_package(update.check(root))
    choice = resolve_consent(state, force="--consent" in sys.argv[2:])
    if "--remove-data" in sys.argv[2:]:
        try:
            removal.ask(state, server=sync_server())
        except Exception as error:  # the notebooks still start; the student can try again
            print(f"The removal page could not be shown ({error}).")
    fetch_course_files(root, state)
    port = free_port()
    remember_port(state, port)
    env = marimo_env(os.environ, state, choice)
    print(f"Starting the notebooks at http://localhost:{port} (close this window to stop them)")
    process = subprocess.Popen(build_command(root, port), env=env)
    job = tie_to_this_process(process)  # noqa: F841  (kept alive on purpose: closing it ends the server)
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
