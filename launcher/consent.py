"""Asks a student, once, whether their anonymised analyses may be shared with the course. Standard library only."""
from __future__ import annotations

import json
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

CONSENT_VERSION = 1  # raise it when the consent text changes: everyone is asked again
CHOICES = ("accepted", "declined")


def consent_file(state: Path) -> Path:
    return Path(state) / "consent.json"


def load(state: Path) -> str | None:
    """The saved answer, or None when there is none, it is unreadable, or it was given for an older consent text."""
    try:
        record = json.loads(consent_file(state).read_text(encoding="utf8"))
        if record["version"] != CONSENT_VERSION or record["choice"] not in CHOICES:
            return None
        return record["choice"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save(state: Path, choice: str) -> None:
    if choice not in CHOICES:
        raise ValueError(f"unknown consent choice: {choice!r}")
    Path(state).mkdir(parents=True, exist_ok=True)
    record = {"version": CONSENT_VERSION, "choice": choice, "at": datetime.now().astimezone().isoformat(timespec="seconds")}
    consent_file(state).write_text(json.dumps(record), encoding="utf8")


PAGE_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Help us make this course better</title>
<style>
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; background: #f3f4f6; color: #1f2937; margin: 0;
         min-height: 100vh; display: grid; place-items: center; }
  main { background: #fff; max-width: 34rem; margin: 1rem; padding: 2rem 2.2rem; border-radius: 14px;
         box-shadow: 0 6px 24px rgba(0, 0, 0, .1); }
  h1 { font-size: 1.5rem; margin: 0 0 .6rem; }
  p { line-height: 1.5; margin: .6rem 0; }
  details { margin: .8rem 0 1.4rem; }
  summary { cursor: pointer; color: #2563eb; }
  details ul { line-height: 1.5; padding-left: 1.2rem; }
  .buttons { display: grid; grid-template-columns: 1fr 1fr; gap: .8rem; }  /* equal columns: both choices the same size */
  @media (max-width: 30rem) { .buttons { grid-template-columns: 1fr; } }
  button { font: inherit; font-weight: 600; padding: .8rem 1.3rem; border-radius: 10px; cursor: pointer;
           border: 2px solid #2563eb; }
  #accept { background: #2563eb; color: #fff; }
  #accept:hover { background: #1d4ed8; }
  #decline { background: #fff; color: #2563eb; }
  #decline:hover { background: #eff6ff; }
  .note { font-size: .9rem; color: #4b5563; margin-top: 1rem; }
</style></head>
<body><main>
<div id="ask">
  <h1>Help us make this course better</h1>
  <p>Your analyses, anonymised, show us where students get stuck and what to improve.</p>
  <details><summary>More info</summary>
    <ul>
      <li>Only the <b>analysis steps</b> you run in the notebooks are recorded (what was executed). Not your clicks.</li>
      <li>It is <b>anonymised</b>: your key is anonymous and we keep no list that links keys to people.</li>
      <li>It is used for two things: 1. improving the course; 2. research on tools that support and improve exploratory analysis.</li>
      <li>It is <b>optional</b>. If you say no, everything works the same, your work just stays on your computer.</li>
      <li>You are asked only once. You can change your mind any time by double-clicking <b>Change-my-answer</b> in the course folder.</li>
    </ul>
  </details>
  <div class="buttons">
    <button id="accept" autofocus>Yes, help improve the course</button>
    <button id="decline">No thanks</button>
  </div>
  <p class="note">One click. You won't see this again, and nothing changes if you say no.</p>
</div>
<div id="thanks" hidden><h1>Thanks!</h1><p>You can close this tab. Your notebooks are opening in a new tab.</p></div>
</main>
<script>
  let answered = false;
  async function answer(choice) {
    const response = await fetch("/answer", { method: "POST", body: "choice=" + choice });
    if (!response.ok) return;
    answered = true;
    document.getElementById("ask").hidden = true;
    document.getElementById("thanks").hidden = false;
  }
  document.getElementById("accept").onclick = () => answer("accepted");
  document.getElementById("decline").onclick = () => answer("declined");
  addEventListener("pagehide", () => { if (!answered) navigator.sendBeacon("/closed"); });
</script></body></html>
"""


class _Page:
    """What the page's requests tell the waiting launcher."""

    def __init__(self, state: Path):
        self.state = state
        self.choice: str | None = None
        self.closed_at: float | None = None


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
            if self.path == "/answer":
                choice = (parse_qs(body).get("choice") or [""])[0]
                if choice not in CHOICES:
                    return self._reply(400, b"unknown choice")
                save(page.state, choice)
                self._reply(200, b"ok")
                page.choice = choice  # only after the reply, so the page always gets its answer before the server stops
                return
            self._reply(404)

    return Handler


def ask(state: Path, open_browser=webbrowser.open, timeout: float = 600.0, grace: float = 3.0) -> str:
    """Shows the consent page and waits. Returns "accepted" or "declined" (both saved), or "undecided" (nothing saved) when the
    student closes the tab without answering or does not answer within `timeout` seconds."""
    page = _Page(Path(state))
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(page))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    try:
        if not open_browser(url):
            print(f"Open this address in your browser to continue: {url}")
        deadline = time.monotonic() + timeout
        while page.choice is None:
            now = time.monotonic()
            closed_at = page.closed_at
            if now > deadline or (closed_at is not None and now - closed_at > grace):
                return "undecided"
            time.sleep(0.05)
        return page.choice
    finally:
        server.shutdown()
        server.server_close()
