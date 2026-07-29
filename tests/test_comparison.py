import io
from pathlib import Path

from datary.comparison import compare_sessions
from datary.models import RecordOptions
from datary.recorder import record_stream


def test_comparison_goal(tmp_path: Path) -> None:
    record_stream(io.StringIO('{"x":2}\n{"x":4}\n'), RecordOptions("a", tmp_path, "jsonl"))
    record_stream(io.StringIO('{"x":1}\n{"x":2}\n'), RecordOptions("b", tmp_path, "jsonl"))
    result = compare_sessions([tmp_path / "a", tmp_path / "b"], ["x"], "lower:x")
    assert result.fields["x"]["improvement_percent_vs_first"][str(tmp_path / "b")] == 50


def test_no_goal_is_honest(tmp_path: Path) -> None:
    for name in ("a", "b"):
        record_stream(io.StringIO('{"x":1}\n'), RecordOptions(name, tmp_path, "jsonl"))
    result = compare_sessions([tmp_path / "a", tmp_path / "b"])
    assert "no comparison goal" in result.warnings[0]

