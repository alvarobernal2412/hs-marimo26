"""The event log that is not public: the launcher fetches it from the course server with the course code (launcher/coursefiles.py).
A small real HTTP server stands in for the course server, so the request the launcher sends is the one that is checked."""
import hashlib
import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "launcher"))
import coursefiles  # noqa: E402

LOG = b"the private event log"
CODE = "course-code"


@pytest.fixture
def course_server():
    """Serves /v1/files/log.parquet to the course code, like provenance-sync. `server.answers` can force a status."""
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            seen.append((self.path, self.headers.get("Authorization")))
            status = server.force or (200 if self.headers.get("Authorization") == f"Bearer {CODE}" else 401)
            body = server.body if status == 200 else b"{}"
            if status == 200 and self.path != "/v1/files/log.parquet":
                status, body = 404, b"{}"
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.force, server.body, server.seen = None, LOG, seen
    server.url = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server
    server.shutdown()
    server.server_close()


def package(tmp_path, content=LOG):
    """A runtime folder whose package names one private file."""
    data = tmp_path / "runtime" / "notebooks" / "data"
    data.mkdir(parents=True)
    (data / "log.parquet.sha256").write_text(hashlib.sha256(content).hexdigest() + "\n", encoding="utf8")
    (data / "public.csv").write_text("a,b")
    return tmp_path / "runtime", data / "log.parquet"


def _must_not_ask(try_code):
    raise AssertionError("the course code page must not be shown")


# ---- what is missing --------------------------------------------------------------------------------------------------------
def test_a_package_without_private_files_needs_nothing(tmp_path):
    (tmp_path / "notebooks" / "data").mkdir(parents=True)
    assert coursefiles.wanted(tmp_path) == {} and coursefiles.ensure(tmp_path, tmp_path / "state", "http://unused", ask=_must_not_ask) == "none"


def test_the_named_file_is_missing_until_it_is_there_with_the_named_hash(tmp_path):
    root, log = package(tmp_path)
    assert list(coursefiles.missing(root)) == [log]
    log.write_bytes(b"another version")
    assert list(coursefiles.missing(root)) == [log]
    log.write_bytes(LOG)
    assert coursefiles.missing(root) == {}


# ---- one download ------------------------------------------------------------------------------------------------------------
def test_fetch_sends_the_code_and_writes_the_file(tmp_path, course_server):
    root, log = package(tmp_path)
    assert coursefiles.fetch(course_server.url, CODE, log, hashlib.sha256(LOG).hexdigest()) == "ok"
    assert log.read_bytes() == LOG
    assert course_server.seen == [("/v1/files/log.parquet", f"Bearer {CODE}")]
    assert not log.with_name("log.parquet.part").exists()


@pytest.mark.parametrize("status, said", [(401, "refused"), (429, "wait"), (404, "failed"), (500, "failed")])
def test_fetch_says_why_it_did_not_work_and_leaves_no_file(tmp_path, course_server, status, said):
    root, log = package(tmp_path)
    course_server.force = status
    assert coursefiles.fetch(course_server.url, CODE, log, hashlib.sha256(LOG).hexdigest()) == said
    assert not log.exists() and not log.with_name("log.parquet.part").exists()


def test_fetch_fails_without_a_connection(tmp_path):
    root, log = package(tmp_path)
    assert coursefiles.fetch("http://127.0.0.1:9", CODE, log, hashlib.sha256(LOG).hexdigest()) == "failed"
    assert not log.exists()


def test_a_file_that_is_not_the_named_one_never_replaces_what_is_there(tmp_path, course_server):
    root, log = package(tmp_path)
    log.write_bytes(b"older but whole")
    course_server.body = b"cut sho"
    assert coursefiles.fetch(course_server.url, CODE, log, hashlib.sha256(LOG).hexdigest()) == "failed"
    assert log.read_bytes() == b"older but whole"


# ---- ensure ------------------------------------------------------------------------------------------------------------------
def test_nothing_is_asked_or_fetched_when_the_file_is_current(tmp_path, course_server):
    root, log = package(tmp_path)
    log.write_bytes(LOG)
    assert coursefiles.ensure(root, tmp_path / "state", course_server.url, ask=_must_not_ask) == "current"
    assert course_server.seen == []


def test_the_first_start_asks_for_the_code_downloads_and_remembers_it(tmp_path, course_server):
    root, log = package(tmp_path)
    tried = []

    def student(try_code):
        tried.append(try_code("a wrong code"))
        tried.append(try_code(CODE))
        return "downloaded"

    assert coursefiles.ensure(root, tmp_path / "state", course_server.url, ask=student) == "downloaded"
    assert tried == ["refused", "ok"] and log.read_bytes() == LOG
    assert coursefiles.saved_code(tmp_path / "state") == CODE  # the wrong one was never saved


def test_a_release_with_another_version_of_the_file_fetches_it_with_the_saved_code_without_asking(tmp_path, course_server):
    root, log = package(tmp_path)
    log.write_bytes(b"last term's log")
    coursefiles.save_code(tmp_path / "state", CODE)
    assert coursefiles.ensure(root, tmp_path / "state", course_server.url, ask=_must_not_ask) == "downloaded"
    assert log.read_bytes() == LOG


def test_a_saved_code_that_stopped_working_asks_again(tmp_path, course_server):
    root, log = package(tmp_path)
    coursefiles.save_code(tmp_path / "state", "last term's code")
    assert coursefiles.ensure(root, tmp_path / "state", course_server.url, ask=lambda try_code: "skipped") == "skipped"
    assert not log.exists()


def test_fetching_can_be_turned_off(tmp_path):
    root, log = package(tmp_path)
    assert coursefiles.server_url({"HS_FILES_URL": ""}) == ""
    assert coursefiles.ensure(root, tmp_path / "state", "", ask=_must_not_ask) == "none"
    assert coursefiles.server_url({}) == "https://provenance.alvispace.com"


# ---- the page ----------------------------------------------------------------------------------------------------------------
class Asked:
    """Runs coursefiles.ask in a thread with a fake browser that records the page address."""

    def __init__(self, try_code, **kwargs):
        self.url, self.result = None, None
        seen = threading.Event()

        def fake_browser(url):
            self.url = url
            seen.set()
            return True

        self.thread = threading.Thread(target=lambda: setattr(self, "result", coursefiles.ask(try_code, open_browser=fake_browser, **kwargs)))
        self.thread.start()
        assert seen.wait(5), "ask never opened the browser"

    def get(self) -> str:
        with urllib.request.urlopen(self.url, timeout=5) as r:
            return r.read().decode("utf8")

    def post(self, path, body=b""):
        return urllib.request.urlopen(urllib.request.Request(self.url + path, data=body, method="POST"), timeout=5)

    def code(self, code) -> str:
        return json.loads(self.post("code", json.dumps({"code": code}).encode()).read())["result"]

    def finish(self):
        self.thread.join(5)
        assert not self.thread.is_alive()
        return self.result


def test_the_page_is_on_loopback_and_says_what_is_asked_and_what_skipping_means():
    asked = Asked(lambda code: "ok")
    html = asked.get()
    assert asked.url.startswith("http://127.0.0.1:")
    assert "course code" in html and "Download the event log" in html and "Not now" in html
    assert "lecture notebooks still work" in html and "asked again the next time you start" in html
    asked.post("skip")
    assert asked.finish() == "skipped"


def test_a_wrong_code_keeps_the_page_and_the_right_one_ends_it():
    asked = Asked(lambda code: "ok" if code == CODE else "refused")
    assert asked.code("guess") == "refused"
    assert asked.thread.is_alive()
    assert asked.code(CODE) == "ok"
    assert asked.finish() == "downloaded"


def test_an_empty_code_is_not_tried():
    tried = []
    asked = Asked(lambda code: tried.append(code) or "ok")
    with pytest.raises(urllib.error.HTTPError):
        asked.post("code", json.dumps({"code": "  "}).encode())
    assert tried == []
    asked.post("skip")
    asked.finish()


def test_closing_the_tab_or_not_answering_starts_without_the_log():
    asked = Asked(lambda code: "ok", grace=0.1)
    asked.post("closed")
    assert asked.finish() == "skipped"
    assert Asked(lambda code: "ok", timeout=0.2).finish() == "skipped"
