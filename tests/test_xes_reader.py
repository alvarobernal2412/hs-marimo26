import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notebooks" / "lib"))
import xes_reader  # noqa: E402

VERBATIM = """<?xml version="1.0" encoding="UTF-8" ?>
<log xes.version="2.0">
\t<trace>
\t\t<string key="case_concept_name" value="A1"/>
\t\t<float key="case_RequestedAmount" value="20000.0"/>
\t\t<event>
\t\t\t<string key="concept_name" value="A_Create"/>
\t\t\t<date key="time_timestamp" value="2016-01-01T09:51:15.304+00:00"/>
\t\t</event>
\t\t<event>
\t\t\t<string key="concept_name" value="A_Submit"/>
\t\t\t<date key="time_timestamp" value="2016-01-01T09:52:15.304+01:00"/>
\t\t</event>
\t</trace>
</log>
"""


def test_verbatim_keeps_keys_as_written(tmp_path):
    path = tmp_path / "log.xes"
    path.write_text(VERBATIM, encoding="utf8")
    log = xes_reader.read_xes(str(path), verbatim=True)
    assert list(log.columns) == ["case_concept_name", "case_RequestedAmount", "concept_name", "time_timestamp"]
    assert log["case_concept_name"].tolist() == ["A1", "A1"]
    assert str(log["time_timestamp"].dtype) == "datetime64[us, UTC]"
    assert log["time_timestamp"].iloc[1] == pd.Timestamp("2016-01-01T08:52:15.304", tz="UTC")


def test_default_mode_unchanged_for_standard_keys(tmp_path):
    path = tmp_path / "std.xes"
    path.write_text(
        '<log><trace><string key="concept:name" value="A1"/><event><string key="concept:name" value="x"/>'
        '<date key="time:timestamp" value="2016-01-01T09:51:15.304+00:00"/></event></trace></log>',
        encoding="utf8",
    )
    log = xes_reader.read_xes(str(path))
    assert {"case:concept:name", "concept:name", "time:timestamp"} <= set(log.columns)


def test_load_event_log_puts_case_lifecycle_last(tmp_path):
    import initial_analysis_kit as ak

    path = tmp_path / "d.xes"
    path.write_text(
        '<log><trace><string key="case_concept_name" value="A1"/><event><string key="case_lifecycle" value="A1, complete"/>'
        '<string key="concept_name" value="x"/><date key="time_timestamp" value="2016-01-01T09:51:15.304+00:00"/></event></trace></log>',
        encoding="utf8",
    )
    assert list(ak.load_event_log(path).columns)[-1] == "case_lifecycle"
