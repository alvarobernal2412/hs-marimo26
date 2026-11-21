"""Tells a student, in the browser, that a new course package is needed and how to get it. Standard library only.

The updater brings new notebooks by itself. A release that changes the package (its Python or its libraries) cannot arrive that
way: the student pastes the install line again. The launcher's own window says so too, but that is a window students rarely read.
"""
from __future__ import annotations

import html
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RELEASES = "https://github.com/alvarobernal2412/hs-marimo26/releases/latest/download"


def install_line(platform: str = sys.platform) -> str:
    """The line a student pastes into a terminal (the same one START-HERE.txt and the release notes give)."""
    if platform == "win32":
        return f'powershell -ExecutionPolicy Bypass -c "irm {RELEASES}/install.ps1 | iex"'
    return f"curl -fsSL {RELEASES}/install.sh | bash"


PAGE_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>A new version of the course tools</title>
<style>
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; background: #f3f4f6; color: #1f2937; margin: 0;
         min-height: 100vh; display: grid; place-items: center; }
  main { background: #fff; max-width: 38rem; margin: 1rem; padding: 2rem 2.2rem; border-radius: 14px;
         box-shadow: 0 6px 24px rgba(0, 0, 0, .1); }
  h1 { font-size: 1.5rem; margin: 0 0 .6rem; }
  p, li { line-height: 1.5; }
  ol { padding-left: 1.2rem; }
  code { display: block; background: #f3f4f6; border-radius: 8px; padding: .7rem .8rem; margin: .5rem 0; font-size: .85rem;
         overflow-wrap: anywhere; user-select: all; }
  button { font: inherit; font-weight: 600; padding: .6rem 1.1rem; border-radius: 10px; cursor: pointer; border: 2px solid #2563eb; }
  #copy { background: #2563eb; color: #fff; }
  #continue { background: #fff; color: #2563eb; margin-top: .6rem; }
  .note { font-size: .9rem; color: #4b5563; }
</style></head>
<body><main>
<div id="tell">
  <h1>A new version of the course tools is available</h1>
  <p>The newest notebooks need it. Getting it takes a few minutes, and your work stays as it is.</p>
  <ol>
    <li>Close this tab and the __WINDOW__ that opened with it.</li>
    <li>Open __TERMINAL__ and paste this line, then press Enter:
      <code id="line">__LINE__</code>
      <button id="copy">Copy the line</button></li>
  </ol>
  <p class="note">START-HERE.txt in the course folder explains how to open __TERMINAL__.</p>
  <button id="continue">Continue with the version I have</button>
</div>
<div id="going" hidden><h1>Starting the version you have</h1><p>You can close this tab. Your notebooks are opening in a new tab.</p></div>
</main>
<script>
  let answered = false;
  document.getElementById("copy").onclick = async () => {
    try { await navigator.clipboard.writeText(document.getElementById("line").textContent);
          document.getElementById("copy").textContent = "Copied"; } catch (e) {}
  };
  document.getElementById("continue").onclick = async () => {
    const response = await fetch("/continue", { method: "POST" });
    if (!response.ok) return;
    answered = true;
    document.getElementById("tell").hidden = true;
    document.getElementById("going").hidden = false;
  };
  addEventListener("pagehide", () => { if (!answered) navigator.sendBeacon("/closed"); });
</script></body></html>
"""


def page_html(platform: str = sys.platform) -> str:
    windows = platform == "win32"
    return (
        PAGE_HTML.replace("__LINE__", html.escape(install_line(platform)))
        .replace("__WINDOW__", "black window" if windows else "Terminal window")
        .replace("__TERMINAL__", "PowerShell" if windows else "Terminal")
    )


def show(open_browser=webbrowser.open, timeout: float = 600.0, grace: float = 3.0, platform: str = sys.platform) -> None:
    """Shows the page and waits until the student presses Continue, closes the tab, or `timeout` seconds pass. The notebooks
    start afterwards in every case: an old version that works is better than none."""
    seen = {"continue": False, "closed_at": None}

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
            seen["closed_at"] = None  # a reload, not a closed tab
            self._reply(200, page_html(platform).encode("utf8"), "text/html; charset=utf-8")

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if self.path == "/closed":
                seen["closed_at"] = time.monotonic()
                return self._reply(204)
            if self.path == "/continue":
                self._reply(200, b"ok")
                seen["continue"] = True  # only after the reply, so the page always gets its answer before the server stops
                return
            self._reply(404)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    try:
        if not open_browser(url):
            print(f"Open this address in your browser to continue: {url}")
        deadline = time.monotonic() + timeout
        while not seen["continue"]:
            now = time.monotonic()
            closed_at = seen["closed_at"]
            if now > deadline or (closed_at is not None and now - closed_at > grace):
                return
            time.sleep(0.05)
    finally:
        server.shutdown()
        server.server_close()
