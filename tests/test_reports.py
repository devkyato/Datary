import io
import json
from pathlib import Path

from datary.models import RecordOptions
from datary.recorder import record_stream
from datary.reports import write_report
from datary.sessions import Session


def test_reports(tmp_path: Path) -> None:
    session = Session.open(
        record_stream(io.StringIO('{"x":1}\n'), RecordOptions("demo", tmp_path, "jsonl"))
    )
    markdown = write_report(session, tmp_path / "report.md")
    assert "# Datary report: demo" in markdown.read_text(encoding="utf-8")
    json_path = write_report(session, tmp_path / "report.json", "json")
    assert json.loads(json_path.read_text(encoding="utf-8"))["session"]["session_name"] == "demo"


def test_markdown_escapes_html_and_displays_integrity_failures(tmp_path: Path) -> None:
    session = Session.open(
        record_stream(
            io.StringIO('{"<script>alert(1)</script>":1}\n'),
            RecordOptions("safe-report", tmp_path, "jsonl"),
        )
    )
    (session.path / "raw.log").write_text("tampered", encoding="utf-8")
    text = write_report(session, tmp_path / "safe.md").read_text(encoding="utf-8")
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "FAILED" in text
    assert "hash mismatch" in text


def test_report_contains_engineering_metrics(tmp_path: Path) -> None:
    session = Session.open(
        record_stream(
            io.StringIO('{"t":0,"target":1,"response":0}\n{"t":1,"target":1,"response":1}\n'),
            RecordOptions(
                "engineering",
                tmp_path,
                "jsonl",
                time_field="t",
                target_field="target",
                response_field="response",
            ),
        )
    )
    text = write_report(session, tmp_path / "engineering.md").read_text(encoding="utf-8")
    assert "Engineering metrics" in text
    assert "mean\\_absolute\\_error" in text
