import hashlib
import json
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "launcher"))
sys.path.insert(0, str(ROOT / "notebooks" / "lib"))
import initial_analysis_kit as ak  # noqa: E402
import removal  # noqa: E402

REAL_URLOPEN = urllib.request.urlopen  # the page tests patch urlopen for the launcher; their own client must stay real

KEY = "student-key-1"
SERVER = "https://provenance.example"


class FakeResponse:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return b"{}"


class FakeOpener:
    """Answers every request with one status (or raises); records the requests."""

    def __init__(self, status=200, error=None):
        self.status, self.error, self.requests = status, error, []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if self.status >= 400:
            raise urllib.error.HTTPError(request.full_url, self.status, "x", {}, None)
        return FakeResponse(self.status)


def make_folders(state: Path, *notebooks: str) -> dict[str, Path]:
    folders = {}
    for nb in notebooks:
        folder = removal.local_folder(state, KEY, nb)
        folder.mkdir(parents=True)
        (folder / "events.jsonl").write_text("x")
        folder.with_name(folder.name + ".sync.json").write_text("{}")
        folders[nb] = folder
    return folders


def sidecar(folder: Path) -> Path:
    return folder.with_name(folder.name + ".sync.json")


def test_the_local_folder_matches_the_notebooks(tmp_path, monkeypatch):
    state = tmp_path / "state"
    monkeypatch.setenv("PMPROV_DIR", str(state / "provenance"))
    for nb in removal.NOTEBOOKS:
        assert removal.local_folder(state, KEY, nb) == ak.session_folder(KEY, nb)
    name = hashlib.sha256(f"{KEY}/map-explorer".encode()).hexdigest()[:16]
    assert removal.local_folder(state, KEY, "map-explorer") == state / "synced" / name


def test_only_the_chosen_notebook_is_set_aside(tmp_path):
    folders = make_folders(tmp_path, "initial-analysis", "map-explorer")
    opener = FakeOpener(200)
    assert removal.remove(tmp_path, KEY, ["map-explorer"], server=SERVER, opener=opener) == {"map-explorer": "removed"}
    assert not folders["map-explorer"].exists() and not sidecar(folders["map-explorer"]).exists()
    moved = list(folders["map-explorer"].parent.glob(folders["map-explorer"].name + ".removed-*"))
    assert len(moved) == 1 and (moved[0] / "events.jsonl").read_text() == "x"
    assert folders["initial-analysis"].is_dir() and sidecar(folders["initial-analysis"]).exists()
    assert len(opener.requests) == 1
    request = opener.requests[0]
    assert request.get_method() == "DELETE"
    assert request.full_url == f"{SERVER}/n/map-explorer/v1/provenance"
    assert request.get_header("Authorization") == f"Bearer {KEY}"


def test_nothing_on_the_server_still_cleans_the_laptop(tmp_path):
    folders = make_folders(tmp_path, "map-explorer")
    assert removal.remove(tmp_path, KEY, ["map-explorer"], server=SERVER, opener=FakeOpener(404)) == {"map-explorer": "nothing"}
    assert not folders["map-explorer"].exists() and not sidecar(folders["map-explorer"]).exists()
    assert list(folders["map-explorer"].parent.glob("*.removed-*"))


def test_a_notebook_without_a_local_folder_is_fine(tmp_path):
    assert removal.remove(tmp_path, KEY, ["map-explorer"], server=SERVER, opener=FakeOpener(200)) == {"map-explorer": "removed"}


@pytest.mark.parametrize("opener, expected", [
    (FakeOpener(401), "unauthorized"), (FakeOpener(403), "unauthorized"), (FakeOpener(429), "unauthorized"),
    (FakeOpener(423), "closed"),
    (FakeOpener(500), "offline"),
    (FakeOpener(error=urllib.error.URLError("down")), "offline"),
    (FakeOpener(error=TimeoutError()), "offline"),
])
def test_a_failed_removal_changes_nothing_locally(tmp_path, opener, expected):
    folders = make_folders(tmp_path, "map-explorer")
    assert removal.remove(tmp_path, KEY, ["map-explorer"], server=SERVER, opener=opener) == {"map-explorer": expected}
    assert folders["map-explorer"].is_dir() and sidecar(folders["map-explorer"]).exists()
    assert not list(folders["map-explorer"].parent.glob("*.removed-*"))


def test_a_local_folder_that_cannot_move_does_not_undo_the_removal(tmp_path, monkeypatch):
    folders = make_folders(tmp_path, "map-explorer")

    def locked(src, dst):
        raise PermissionError("in use")

    monkeypatch.setattr(removal.shutil, "move", locked)
    assert removal.remove(tmp_path, KEY, ["map-explorer"], server=SERVER, opener=FakeOpener(200)) == {"map-explorer": "removed"}
    assert folders["map-explorer"].is_dir()


# ---- the page --------------------------------------------------------------------------------------------------------------
class Asked:
    def __init__(self, state, opener=None, **kwargs):
        self.url, self.result = None, None
        self._seen = threading.Event()

        def fake_browser(url):
            self.url = url
            self._seen.set()
            return True

        self.thread = threading.Thread(
            target=lambda: setattr(self, "result", removal.ask(state, open_browser=fake_browser, server=SERVER, **{"timeout": 20, **kwargs})))
        self.thread.start()
        assert self._seen.wait(5)

    def get(self, path=""):
        with REAL_URLOPEN(self.url + path, timeout=5) as r:
            return r.read().decode("utf8")

    def post(self, path, body=b""):
        return REAL_URLOPEN(urllib.request.Request(self.url + path, data=body, method="POST"), timeout=5)

    def finish(self):
        self.thread.join(5)
        assert not self.thread.is_alive()
        return self.result


def test_the_page_requires_a_key_and_a_notebook(tmp_path, monkeypatch):
    opener = FakeOpener(200)
    monkeypatch.setattr(removal.urllib.request, "urlopen", opener)
    asked = Asked(tmp_path, grace=0.3)
    for body in (b"notebook=map-explorer", b"key=%20%20&notebook=map-explorer", b"key=abc", b"key=abc&notebook=nope"):
        with pytest.raises(urllib.error.HTTPError) as err:
            asked.post("remove", body)
        assert err.value.code == 400
    assert opener.requests == []
    asked.post("closed")
    assert asked.finish() is None


def test_the_page_texts(tmp_path):
    asked = Asked(tmp_path, grace=0.3)
    html = asked.get()
    assert "Remove my saved data" in html
    assert "The course server keeps a copy for your teachers. The notebook you pick starts empty and keeps saving." in html
    for title in removal.NOTEBOOKS.values():
        assert title in html
    assert " checked" not in html
    asked.post("closed")
    asked.finish()


def test_removing_through_the_page_returns_the_result(tmp_path, monkeypatch):
    opener = FakeOpener(200)
    monkeypatch.setattr(removal.urllib.request, "urlopen", opener)
    folders = make_folders(tmp_path, "map-explorer")
    asked = Asked(tmp_path)
    body = urllib.parse.urlencode({"key": f" {KEY} ", "notebook": "map-explorer"}).encode()
    with asked.post("remove", body) as response:
        assert json.loads(response.read())["results"] == {"map-explorer": "removed"}
    assert asked.finish() == {"map-explorer": "removed"}
    assert not folders["map-explorer"].exists()
    assert opener.requests[0].get_header("Authorization") == f"Bearer {KEY}"
