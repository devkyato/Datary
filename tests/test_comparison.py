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


def test_duplicate_source_labels_do_not_overwrite(tmp_path: Path) -> None:
    session = record_stream(io.StringIO('{"x":1}\n'), RecordOptions("same", tmp_path, "jsonl"))
    result = compare_sessions([session, session], ["x"])
    assert list(result.fields["x"]["means"]) == [str(session), f"{session}#2"]


def test_unit_mismatch_blocks_goal_claim(tmp_path: Path) -> None:
    first = record_stream(
        io.StringIO('{"x":1}\n'),
        RecordOptions("metres", tmp_path, "jsonl", units={"x": "m"}),
    )
    second = record_stream(
        io.StringIO('{"x":2}\n'),
        RecordOptions("seconds", tmp_path, "jsonl", units={"x": "s"}),
    )
    result = compare_sessions([first, second], ["x"], "higher:x")
    assert result.fields["x"]["comparable"] is False
    assert "improvement_percent_vs_first" not in result.fields["x"]
    assert any("incompatible declared units" in warning for warning in result.warnings)


def test_different_sampling_rates_are_not_claimed_comparable(tmp_path: Path) -> None:
    first = record_stream(
        io.StringIO('{"t":0,"x":2}\n{"t":1,"x":2}\n{"t":2,"x":2}\n'),
        RecordOptions("slow", tmp_path, "jsonl", time_field="t"),
    )
    second = record_stream(
        io.StringIO(
            '{"t":0,"x":1}\n{"t":0.5,"x":1}\n{"t":1,"x":1}\n{"t":1.5,"x":1}\n{"t":2,"x":1}\n'
        ),
        RecordOptions("fast", tmp_path, "jsonl", time_field="t"),
    )
    result = compare_sessions([first, second], ["x"], "lower:x")
    assert result.fields["x"]["comparable"] is False
    assert "improvement_percent_vs_first" not in result.fields["x"]
    assert result.timing["shared_relative_range"] == [0.0, 2.0]
    assert any("sampling rates differ" in warning for warning in result.warnings)
