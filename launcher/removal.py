"""Lets a student remove their saved work in a notebook, from the course server and from this computer. Standard library only."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from coursefiles import SERVER

NOTEBOOKS: dict[str, str] = {"initial-analysis": "01 Assignment - Initial Analysis", "map-explorer": "03 Assignment - Process Map"}


def local_folder(state: Path, key: str, notebook: str) -> Path:
    """Where the notebooks keep this key's work in this notebook (same name as `initial_analysis_kit.session_folder`)."""
    return Path(state) / "synced" / hashlib.sha256(f"{key}/{notebook}".encode()).hexdigest()[:16]


def _server_removal(server: str, key: str, notebook: str, opener) -> tuple[str, int | None]:
    """What the server did ("removed", "nothing", ...) and, for "removed", the revision of the removal when it said one."""
    request = urllib.request.Request(
        f"{server.rstrip('/')}/n/{notebook}/v1/provenance", method="DELETE", headers={"Authorization": f"Bearer {key}"})
    try:
        with opener(request, timeout=30) as response:
            if response.status != 200:
                return "offline", None
            try:
                revision = json.loads(response.read()).get("revision")
            except (ValueError, AttributeError):
                revision = None
            return "removed", revision if isinstance(revision, int) and not isinstance(revision, bool) and revision >= 0 else None
    except urllib.error.HTTPError as error:
        return {404: "nothing", 401: "unauthorized", 403: "unauthorized", 429: "unauthorized", 423: "closed"}.get(error.code, "offline"), None
    except Exception:  # network down, timeout, a broken answer: nothing was changed as far as the student can tell
        return "offline", None


def _set_aside(state: Path, key: str, notebook: str, revision: int | None = None) -> bool:
    """Moves this notebook's local folder to `<folder>.removed-<UTC stamp>`. Its `.sync.json` is rewritten to say "this key's work
    is at the removal's revision, nothing saved yet" (what the notebook's `Sync` writes), so the next save builds on the removal;
    without that revision it is deleted. False when the move failed."""
    folder = local_folder(state, key, notebook)
    sidecar = folder.with_name(folder.name + ".sync.json")
    try:
        if folder.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            # a rename in the same directory: complete or an error, where shutil.move falls back to copying and deleting
            os.replace(folder, folder.with_name(f"{folder.name}.removed-{stamp}"))
        if revision is None:
            sidecar.unlink(missing_ok=True)
        else:
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            record = {"key_hash": hashlib.sha256(key.encode()).hexdigest(), "revision": revision, "sha256": ""}
            sidecar.write_text(json.dumps(record), encoding="utf-8")
        return True
    except OSError:  # e.g. the notebooks are open: the notebook sets the copy aside itself when it next opens
        return False


def _remove(state: Path, key: str, notebooks: list[str], server: str, opener) -> tuple[dict[str, str], list[str]]:
    results: dict[str, str] = {}
    kept_here: list[str] = []
    for notebook in notebooks:
        results[notebook], revision = _server_removal(server, key, notebook, opener)
        if results[notebook] in ("removed", "nothing") and not _set_aside(state, key, notebook, revision):
            kept_here.append(notebook)
    return results, kept_here


def remove(state: Path, key: str, notebooks: list[str], server: str = SERVER, opener=urllib.request.urlopen) -> dict[str, str]:
    """Removes the key's work in each notebook from the server, then sets the local copy aside (never deletes it). Per notebook:
    "removed", "nothing" (the server had none), "unauthorized", "closed" or "offline". Only the first two touch this computer."""
    return _remove(Path(state), key, notebooks, server, opener)[0]


def _checkboxes() -> str:
    return "\n".join(
        f'    <label><input type="checkbox" name="notebook" value="{name}"> {title}</label>' for name, title in NOTEBOOKS.items())


PAGE_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Remove my saved data</title>
<style>
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; background: #f3f4f6; color: #1f2937; margin: 0;
         min-height: 100vh; display: grid; place-items: center; }
  main { background: #fff; max-width: 34rem; margin: 1rem; padding: 2rem 2.2rem; border-radius: 14px;
         box-shadow: 0 6px 24px rgba(0, 0, 0, .1); }
  h1 { font-size: 1.5rem; margin: 0 0 .6rem; }
  p { line-height: 1.5; margin: .6rem 0; }
  label { display: block; margin: .5rem 0; }
  input[type=text] { font: inherit; width: 100%; box-sizing: border-box; padding: .5rem; border: 1px solid #9ca3af; border-radius: 8px; }
  button { font: inherit; font-weight: 600; padding: .7rem 1.3rem; border-radius: 10px; cursor: pointer; border: 2px solid #b91c1c;
           background: #b91c1c; color: #fff; margin-top: .8rem; }
  button.plain { background: #fff; color: #b91c1c; }
  .error { color: #b91c1c; }
</style></head>
<body><main>
<div id="form">
  <h1>Remove my saved data</h1>
  <p>The course server keeps a copy for your teachers. The notebook you pick starts empty and keeps saving.</p>
  <p><label for="key">Your key</label><input type="text" id="key" autocomplete="off" autofocus></p>
  <fieldset style="border:0;padding:0;margin:0">
@CHECKBOXES@
  </fieldset>
  <p class="error" id="problem" hidden></p>
  <button id="remove">Remove</button>
</div>
<div id="confirm" hidden>
  <h1>Are you sure?</h1>
  <p>This removes your saved work in:</p>
  <ul id="chosen"></ul>
  <button id="yes">Yes, remove it</button> <button id="back" class="plain">Go back</button>
</div>
<div id="done" hidden>
  <h1>Done</h1>
  <div id="results"></div>
  <p>You can close this tab. Your notebooks are opening in a new tab: this can take a minute or two.</p>
</div>
</main>
<script>
  const TITLES = @TITLES@;
  let finished = false;
  const show = (id) => { for (const s of ["form", "confirm", "done"]) document.getElementById(s).hidden = s !== id; };
  const picked = () => [...document.querySelectorAll("input[name=notebook]:checked")].map((box) => box.value);
  document.getElementById("remove").onclick = () => {
    const problem = document.getElementById("problem");
    if (!document.getElementById("key").value.trim()) { problem.textContent = "Paste your key first."; problem.hidden = false; return; }
    if (!picked().length) { problem.textContent = "Tick at least one notebook."; problem.hidden = false; return; }
    problem.hidden = true;
    document.getElementById("chosen").replaceChildren(...picked().map((name) => Object.assign(document.createElement("li"), { textContent: TITLES[name] })));
    show("confirm");
  };
  document.getElementById("back").onclick = () => show("form");
  const say = (name, status, kept) => {
    const title = TITLES[name];
    if (status === "removed" || status === "nothing") {
      return "Your data in " + title + " was removed. It starts empty." +
        (kept ? " The copy on this computer will be set aside when the notebook next opens." : "");
    }
    if (status === "unauthorized") return title + ": The key was not accepted. Check that you pasted it completely.";
    if (status === "closed") return title + ": The course is closed, so nothing can be removed. Ask your teachers.";
    return title + ": The course server could not be reached. Nothing was changed. Try again later.";
  };
  document.getElementById("yes").onclick = async () => {
    const body = new URLSearchParams();
    body.append("key", document.getElementById("key").value.trim());
    for (const name of picked()) body.append("notebook", name);
    const response = await fetch("/remove", { method: "POST", body: body.toString() });
    if (!response.ok) { show("form"); return; }
    const answer = await response.json();
    finished = true;
    document.getElementById("results").replaceChildren(...Object.entries(answer.results).map(([name, status]) =>
      Object.assign(document.createElement("p"), { textContent: say(name, status, answer.kept_here.includes(name)) })));
    show("done");
  };
  addEventListener("pagehide", () => { if (!finished) navigator.sendBeacon("/closed"); });
</script></body></html>
""".replace("@CHECKBOXES@", _checkboxes()).replace("@TITLES@", json.dumps(NOTEBOOKS))


class _Page:
    def __init__(self, state: Path, server: str):
        self.state, self.server = state, server
        self.result: dict[str, str] | None = None
        self.closed_at: float | None = None


def _handler(page: _Page):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
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
            page.closed_at = None
            self._reply(200, PAGE_HTML.encode("utf8"), "text/html; charset=utf-8")

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode("utf8", "replace")
            if self.path == "/closed":
                page.closed_at = time.monotonic()
                return self._reply(204)
            if self.path == "/remove":
                form = urllib.parse.parse_qs(body)
                key = (form.get("key") or [""])[0].strip()
                chosen = [name for name in dict.fromkeys(form.get("notebook") or [])]
                if not key or not chosen or any(name not in NOTEBOOKS for name in chosen):
                    return self._reply(400, b"a key and at least one notebook are needed")
                results, kept_here = _remove(page.state, key, chosen, page.server, urllib.request.urlopen)
                answer = json.dumps({"results": results, "kept_here": kept_here}).encode("utf8")
                self._reply(200, answer, "application/json")
                page.result = results  # only after the reply, so the page gets its answer before the server stops
                return
            self._reply(404)

    return Handler


def ask(state: Path, open_browser=webbrowser.open, timeout: float = 600.0, grace: float = 3.0,
        server: str = SERVER) -> dict[str, str] | None:
    """Shows the removal page and waits. Returns what happened per notebook, or None when the student closes the tab (or does
    not answer within `timeout` seconds) without removing anything."""
    page = _Page(Path(state), server)
    http = ThreadingHTTPServer(("127.0.0.1", 0), _handler(page))
    http.daemon_threads = True
    threading.Thread(target=http.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{http.server_address[1]}/"
    try:
        if not open_browser(url):
            print(f"Open this address in your browser to continue: {url}")
        deadline = time.monotonic() + timeout
        while page.result is None:
            now = time.monotonic()
            closed_at = page.closed_at
            if now > deadline or (closed_at is not None and now - closed_at > grace):
                return None
            time.sleep(0.05)
        return page.result
    finally:
        http.shutdown()
        http.server_close()
