import io
import json
from pathlib import Path

from datary.models import RecordOptions
from datary.recorder import record_stream
from datary.reports import write_report
from datary.sessions import Session


def test_reports(tmp_path: Path) -> None:
    session = Session.open(record_stream(io.StringIO('{"x":1}\n'), RecordOptions("demo", tmp_path, "jsonl")))
    markdown = write_report(session, tmp_path / "report.md")
    assert "# Datary report: demo" in markdown.read_text(encoding="utf-8")
    json_path = write_report(session, tmp_path / "report.json", "json")
    assert json.loads(json_path.read_text(encoding="utf-8"))["session"]["session_name"] == "demo"

