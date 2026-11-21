"""The page that tells a student a new package is needed (launcher/notice.py): shown in the browser, where they look, because
the launcher's own window is one they rarely read."""
import sys
import threading
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "launcher"))
import notice  # noqa: E402
import start  # noqa: E402


class Shown:
    """Runs notice.show in a thread with a fake browser that records the page address."""

    def __init__(self, **kwargs):
        self.url = None
        self._seen = threading.Event()

        def fake_browser(url):
            self.url = url
            self._seen.set()
            return True

        self.thread = threading.Thread(target=lambda: notice.show(open_browser=fake_browser, **kwargs))
        self.thread.start()
        assert self._seen.wait(5), "show never opened the browser"

    def get(self) -> str:
        with urllib.request.urlopen(self.url, timeout=5) as r:
            return r.read().decode("utf8")

    def post(self, path):
        return urllib.request.urlopen(urllib.request.Request(self.url + path, data=b"", method="POST"), timeout=5)

    def finished(self, seconds=5) -> bool:
        self.thread.join(seconds)
        return not self.thread.is_alive()


def test_the_page_gives_the_line_to_paste_for_this_system_and_a_way_to_go_on():
    shown = Shown(platform="win32")
    html = shown.get()
    assert shown.url.startswith("http://127.0.0.1:")
    assert "install.ps1 | iex" in html and "install.sh" not in html
    assert "Continue with the version I have" in html
    shown.post("continue")
    assert shown.finished()

    mac = Shown(platform="darwin")
    assert "install.sh | bash" in mac.get() and "install.ps1" not in mac.get()
    mac.post("continue")
    assert mac.finished()


def test_the_lines_are_the_ones_the_release_notes_give():
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "release.yml").read_text(encoding="utf8")
    for platform in ("win32", "darwin"):
        assert notice.install_line(platform) in workflow.replace("\\`", "`")


def test_a_closed_tab_or_no_answer_lets_the_notebooks_start_anyway():
    closed = Shown(grace=0.2)
    closed.post("closed")
    assert closed.finished()
    assert Shown(timeout=0.3).finished()


def test_the_launcher_shows_it_only_when_a_new_package_is_needed_and_never_fails_because_of_it():
    seen = []
    for result in ("updated", "current", "failed", "unknown"):
        start.tell_about_new_package(result, show=lambda: seen.append(result))
    assert seen == []
    start.tell_about_new_package("needs-package", show=lambda: seen.append("shown"))
    assert seen == ["shown"]

    def broken():
        raise OSError("no browser")

    start.tell_about_new_package("needs-package", show=broken)  # the student still starts
