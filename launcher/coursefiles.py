"""Fetches the course files that are not public: asks the student, once, for the course code. Standard library only.

A private file is not in the package. The package only names it: `notebooks/data/<name>.sha256` holds the hash of `<name>`.
The launcher downloads `<name>` from the course server with the course code and puts it next to that hash file, which is where the
notebooks read it. A release that changes the file changes the hash, and the file is fetched again with the saved code."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SERVER = "https://provenance.alvispace.com"
MARK = ".sha256"


def server_url(env=os.environ) -> str:
    """Where the files come from; `HS_FILES_URL` names another server, and an empty value turns fetching off."""
    return env.get("HS_FILES_URL", SERVER).rstrip("/")


def code_file(state: Path) -> Path:
    return Path(state) / "course-code.txt"


def saved_code(state: Path) -> str:
    try:
        return code_file(state).read_text(encoding="utf8").strip()
    except OSError:
        return ""


def save_code(state: Path, code: str) -> None:
    Path(state).mkdir(parents=True, exist_ok=True)
    code_file(state).write_text(code.strip(), encoding="utf8")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def wanted(root: Path) -> dict[Path, str]:
    """The private files this package names, each with the hash it must have."""
    found = {}
    for mark in sorted((Path(root) / "notebooks" / "data").glob("*" + MARK)):
        try:
            expected = mark.read_text(encoding="utf8").split()[0].lower()
        except (OSError, IndexError):
            continue
        found[mark.with_name(mark.name[: -len(MARK)])] = expected
    return found


def missing(root: Path) -> dict[Path, str]:
    """Those of `wanted` that are not on this computer, or are another version than the package names."""
    return {path: expected for path, expected in wanted(root).items() if not path.is_file() or file_hash(path) != expected}


def fetch(server: str, code: str, path: Path, expected: str, opener=urllib.request.urlopen) -> str:
    """Downloads one file to `path`. Says "ok", "refused" (not the course code), "wait" (too many wrong codes from this address)
    or "failed" (no connection, or not the file the package names). `path` only changes when the whole file arrived intact."""
    request = urllib.request.Request(f"{server}/v1/files/{path.name}", headers={"Authorization": f"Bearer {code}", "User-Agent": "hs-marimo26"})
    part = path.with_name(path.name + ".part")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with opener(request, timeout=120) as response, open(part, "wb") as out:
            for block in iter(lambda: response.read(1024 * 1024), b""):
                out.write(block)
        if file_hash(part) != expected:
            return "failed"
        part.replace(path)
        return "ok"
    except urllib.error.HTTPError as problem:
        return {401: "refused", 429: "wait"}.get(problem.code, "failed")
    except Exception:
        return "failed"
    finally:
        try:
            part.unlink()
        except OSError:
            pass


def fetch_all(server: str, code: str, files: dict[Path, str], opener=urllib.request.urlopen) -> str:
    """"ok" when every file arrived; otherwise what went wrong with the first that did not."""
    for path, expected in files.items():
        result = fetch(server, code, path, expected, opener)
        if result != "ok":
            return result
    return "ok"


PAGE_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>The course event log</title>
<style>
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; background: #f3f4f6; color: #1f2937; margin: 0;
         min-height: 100vh; display: grid; place-items: center; }
  main { background: #fff; max-width: 34rem; margin: 1rem; padding: 2rem 2.2rem; border-radius: 14px;
         box-shadow: 0 6px 24px rgba(0, 0, 0, .1); }
  h1 { font-size: 1.5rem; margin: 0 0 .6rem; }
  p { line-height: 1.5; margin: .6rem 0; }
  input { font: inherit; width: 100%; box-sizing: border-box; padding: .7rem .8rem; border: 2px solid #d1d5db; border-radius: 10px;
          margin: .6rem 0 1rem; }
  input:focus { outline: none; border-color: #2563eb; }
  .buttons { display: grid; grid-template-columns: 1fr 1fr; gap: .8rem; }
  @media (max-width: 30rem) { .buttons { grid-template-columns: 1fr; } #get { order: -1; } }
  button { font: inherit; font-weight: 600; padding: .8rem 1.3rem; border-radius: 10px; cursor: pointer; border: 2px solid #2563eb; }
  button:disabled { opacity: .6; cursor: default; }
  #get { background: #2563eb; color: #fff; }
  #get:hover:enabled { background: #1d4ed8; }
  #skip { background: #fff; color: #2563eb; }
  #skip:hover:enabled { background: #eff6ff; }
  #problem { color: #b91c1c; font-weight: 600; min-height: 1.5rem; }
  .note { font-size: .9rem; color: #4b5563; margin-top: 1rem; }
</style></head>
<body><main>
<div id="ask">
  <h1>The course event log</h1>
  <p>The assignment notebooks work on an event log that is not public. Enter the <b>course code</b> your teachers gave you
     to download it to this computer.</p>
  <input id="code" placeholder="Paste the course code here" autocomplete="off" autofocus>
  <p id="problem" role="alert"></p>
  <div class="buttons">
    <button id="skip">Not now</button>
    <button id="get">Download the event log</button>
  </div>
  <p class="note">You do this once. Without the event log the lecture notebooks still work; the assignment notebooks do not,
     and you are asked again the next time you start.</p>
</div>
<div id="thanks" hidden>
  <h1 id="done">The event log is on your computer</h1>
  <p>Your notebooks are opening in a new tab. <b>This can take a minute or two</b>, longer on a slower laptop: please wait, there
     is no need to start again.</p>
  <p>You can close this tab.</p>
</div>
</main>
<script>
  const PROBLEMS = {
    refused: "That is not the course code. Check it and try again.",
    wait: "Too many wrong codes. Wait ten minutes and try again.",
    failed: "The download did not work. Check your internet connection and try again.",
    empty: "Enter the course code first.",
  };
  let answered = false;
  const get = document.getElementById("get"), skip = document.getElementById("skip"), code = document.getElementById("code");
  const problem = document.getElementById("problem");
  function finish(title) {
    answered = true;
    if (title) document.getElementById("done").textContent = title;
    document.getElementById("ask").hidden = true;
    document.getElementById("thanks").hidden = false;
  }
  get.onclick = async () => {
    if (!code.value.trim()) { problem.textContent = PROBLEMS.empty; return; }
    get.disabled = skip.disabled = true;
    get.textContent = "Downloading...";
    problem.textContent = "";
    let result = "failed";
    try {
      const response = await fetch("/code", { method: "POST", body: JSON.stringify({ code: code.value.trim() }) });
      if (response.ok) result = (await response.json()).result;
    } catch (e) {}
    if (result === "ok") return finish();
    problem.textContent = PROBLEMS[result] || PROBLEMS.failed;
    get.disabled = skip.disabled = false;
    get.textContent = "Download the event log";
  };
  code.onkeydown = (e) => { if (e.key === "Enter") get.onclick(); };
  skip.onclick = async () => {
    const response = await fetch("/skip", { method: "POST" });
    if (response.ok) finish("Starting without the event log");
  };
  addEventListener("pagehide", () => { if (!answered) navigator.sendBeacon("/closed"); });
</script></body></html>
"""


class _Page:
    """What the page's requests tell the waiting launcher."""

    def __init__(self, try_code):
        self.try_code = try_code
        self.result: str | None = None
        self.closed_at: float | None = None
        self.busy = threading.Lock()  # one download at a time, however often the button is pressed


def _handler(page: _Page):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the student's black window quiet
            pass

        def _reply(self, status: int, body: bytes = b"", content_type: str = "text/plain; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.split("?")[0] != "/":
                return self._reply(404)
            page.closed_at = None  # a reload, not a closed tab
            self._reply(200, PAGE_HTML.encode("utf8"), "text/html; charset=utf-8")

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode("utf8", "replace")
            if self.path == "/closed":
                page.closed_at = time.monotonic()
                return self._reply(204)
            if self.path == "/skip":
                self._reply(200, b"ok")
                page.result = "skipped"  # only after the reply, so the page always gets its answer before the server stops
                return
            if self.path == "/code":
                try:
                    code = str(json.loads(body).get("code", "")).strip()
                except (ValueError, AttributeError):
                    code = ""
                if not code:
                    return self._reply(400, b"no code")
                with page.busy:
                    result = page.try_code(code)
                self._reply(200, json.dumps({"result": result}).encode("utf8"), "application/json")
                if result == "ok":
                    page.result = "downloaded"
                return
            self._reply(404)

    return Handler


def ask(try_code, open_browser=webbrowser.open, timeout: float = 900.0, grace: float = 3.0) -> str:
    """Shows the page and waits. `try_code(code)` does the download and says how it went (see `fetch`); the page stays until it says
    "ok". Returns "downloaded", or "skipped" when the student presses "Not now", closes the tab or does not answer in time."""
    page = _Page(try_code)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(page))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    try:
        if not open_browser(url):
            print(f"Open this address in your browser to continue: {url}")
        deadline = time.monotonic() + timeout
        while page.result is None:
            now = time.monotonic()
            closed_at = page.closed_at
            if now > deadline or (closed_at is not None and now - closed_at > grace and not page.busy.locked()):
                return "skipped"
            time.sleep(0.05)
        return page.result
    finally:
        server.shutdown()
        server.server_close()


def ensure(root: Path, state: Path, server: str | None = None, ask=ask, opener=urllib.request.urlopen) -> str:
    """Makes sure the private files of this package are on this computer. Says what happened: "none" (the package names no
    private file, or fetching is turned off), "current", "downloaded" or "skipped" (the student starts without them)."""
    server = server_url() if server is None else server
    files = missing(root) if server else {}
    if not files:
        return "current" if server and wanted(root) else "none"
    code = saved_code(state)
    if code and fetch_all(server, code, files, opener) == "ok":  # a release changed the file: no question, the code is known
        return "downloaded"

    def try_code(entered: str) -> str:
        result = fetch_all(server, entered, missing(root), opener)
        if result == "ok":
            save_code(state, entered)
        return result

    return ask(try_code)
