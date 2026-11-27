"""Adds a `folded_activity` attribute to every event of the Sepsis XES log: `Release` for `Release A` to `Release E`, the
activity's own name for every other activity. It edits the text event by event (the rest of the file stays as it is, line endings
included) and running it again changes nothing.

    python build/add_folded_activity.py [file.xes]
"""

import re
import sys
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[1] / "notebooks" / "data" / "SepsisCases2020EventLog.xes"
EVENT = re.compile(rb"<event>.*?</event>", re.DOTALL)
NAME = re.compile(rb'([ \t]*)<string key="concept:name" value="([^"]*)"/>(\r?\n)')
RELEASES = {f"Release {letter}".encode() for letter in "ABCDE"}


def fold(name: bytes) -> bytes:
    return b"Release" if name in RELEASES else name


def fold_event(match: re.Match) -> bytes:
    block = match.group(0)
    if b'key="folded_activity"' in block:
        return block
    name = NAME.search(block)
    if name is None:
        return block
    line = name.group(1) + b'<string key="folded_activity" value="' + fold(name.group(2)) + b'"/>' + name.group(3)
    return block[: name.end()] + line + block[name.end() :]


def add_folded_activity(path: Path) -> None:
    data = Path(path).read_bytes()
    out = EVENT.sub(fold_event, data)
    if out != data:
        Path(path).write_bytes(out)


if __name__ == "__main__":
    add_folded_activity(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT)
