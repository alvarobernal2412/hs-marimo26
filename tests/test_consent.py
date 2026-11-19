import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "launcher"))
import consent  # noqa: E402


def test_load_is_none_without_file(tmp_path):
    assert consent.load(tmp_path) is None


@pytest.mark.parametrize("choice", ["accepted", "declined"])
def test_save_then_load_roundtrip(tmp_path, choice):
    consent.save(tmp_path, choice)
    assert consent.load(tmp_path) == choice


def test_save_creates_missing_state_dir(tmp_path):
    state = tmp_path / "not" / "there" / "yet"
    consent.save(state, "accepted")
    assert consent.load(state) == "accepted"


def test_save_rejects_unknown_choice(tmp_path):
    with pytest.raises(ValueError):
        consent.save(tmp_path, "maybe")
    assert not consent.consent_file(tmp_path).exists()


def test_load_ignores_corrupt_file(tmp_path):
    consent.consent_file(tmp_path).write_text("{nope", encoding="utf8")
    assert consent.load(tmp_path) is None


def test_load_ignores_older_version(tmp_path):
    record = {"version": consent.CONSENT_VERSION - 1, "choice": "accepted", "at": "2026-11-19"}
    consent.consent_file(tmp_path).write_text(json.dumps(record), encoding="utf8")
    assert consent.load(tmp_path) is None


def test_record_has_version_and_iso_date(tmp_path):
    consent.save(tmp_path, "declined")
    record = json.loads(consent.consent_file(tmp_path).read_text(encoding="utf8"))
    assert record["version"] == consent.CONSENT_VERSION == 1
    assert record["choice"] == "declined"
    datetime.fromisoformat(record["at"])


# ---- the page --------------------------------------------------------------------------------------------------------------
import threading  # noqa: E402
import time  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402


class Asked:
    """Runs consent.ask in a thread with a fake browser that records the page address."""

    def __init__(self, state, browser_opens=True, **kwargs):
        self.url = None
        self.result = None
        self._seen = threading.Event()

        def fake_browser(url):
            self.url = url
            self._seen.set()
            return browser_opens

        self.thread = threading.Thread(target=lambda: setattr(self, "result", consent.ask(state, open_browser=fake_browser, **kwargs)))
        self.thread.start()
        assert self._seen.wait(5), "ask never opened the browser"

    def get(self, path="") -> str:
        with urllib.request.urlopen(self.url + path, timeout=5) as r:
            return r.read().decode("utf8")

    def post(self, path, body=b""):
        return urllib.request.urlopen(urllib.request.Request(self.url + path, data=body, method="POST"), timeout=5)

    def answer(self, choice):
        return self.post("answer", f"choice={choice}".encode())

    def finish(self):
        self.thread.join(5)
        assert not self.thread.is_alive()
        return self.result


def test_page_is_served_on_loopback_only(tmp_path):
    asked = Asked(tmp_path)
    assert asked.url.startswith("http://127.0.0.1:")
    asked.answer("declined")
    asked.finish()


def test_page_shows_both_buttons_with_exact_labels(tmp_path):
    asked = Asked(tmp_path)
    html = asked.get()
    assert "Yes, help improve the course" in html
    assert "No thanks" in html
    assert "autofocus" in html
    asked.answer("declined")
    asked.finish()


def test_accept_returns_accepted_and_saves(tmp_path):
    asked = Asked(tmp_path)
    asked.answer("accepted")
    assert asked.finish() == "accepted"
    assert consent.load(tmp_path) == "accepted"


def test_decline_returns_declined_and_saves(tmp_path):
    asked = Asked(tmp_path)
    asked.answer("declined")
    assert asked.finish() == "declined"
    assert consent.load(tmp_path) == "declined"


def test_unknown_choice_is_400_and_not_saved(tmp_path):
    asked = Asked(tmp_path)
    with pytest.raises(urllib.error.HTTPError) as error:
        asked.answer("maybe")
    assert error.value.code == 400
    assert consent.load(tmp_path) is None
    asked.answer("declined")
    asked.finish()


def test_closing_the_tab_is_undecided_and_not_saved(tmp_path):
    asked = Asked(tmp_path, grace=0.3)
    asked.post("closed")
    assert asked.finish() == "undecided"
    assert consent.load(tmp_path) is None


def test_reload_within_grace_keeps_waiting(tmp_path):
    asked = Asked(tmp_path, grace=0.6)
    asked.post("closed")
    asked.get()  # the page was reloaded, not closed
    time.sleep(1.0)
    assert asked.thread.is_alive()
    asked.answer("accepted")
    assert asked.finish() == "accepted"


def test_timeout_is_undecided(tmp_path):
    asked = Asked(tmp_path, timeout=0.3)
    assert asked.finish() == "undecided"
    assert consent.load(tmp_path) is None


def test_url_is_printed_when_the_browser_cannot_open(tmp_path, capsys):
    asked = Asked(tmp_path, browser_opens=False, timeout=0.3)
    asked.finish()
    assert asked.url in capsys.readouterr().out
