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
