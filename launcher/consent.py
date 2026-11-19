"""Asks a student, once, whether their anonymised analyses may be shared with the course. Standard library only."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

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
