import io
from pathlib import Path

from datary.models import RecordOptions
from datary.recorder import record_stream
from datary.sessions import Session


def test_record_session_and_integrity(tmp_path: Path) -> None:
    path = record_stream(io.StringIO('{"t":0,"x":1}\nbad\n{"t":1,"x":2}\n'), RecordOptions("demo", tmp_path, "jsonl", "t"))
    session = Session.open(path)
    assert session.manifest["valid_record_count"] == 2
    assert session.manifest["invalid_record_count"] == 1
    assert session.manifest["working_directory"] == "<redacted>"
    assert session.verify() == []
    assert (path / "raw.log").read_text(encoding="utf-8").endswith('{"t":1,"x":2}\n')


def test_duplicate_names_and_overwrite(tmp_path: Path) -> None:
    first = record_stream(io.StringIO('{"x":1}\n'), RecordOptions("demo", tmp_path, "jsonl"))
    second = record_stream(io.StringIO('{"x":2}\n'), RecordOptions("demo", tmp_path, "jsonl"))
    assert first.name == "demo"
    assert second.name == "demo-2"
    replaced = record_stream(io.StringIO('{"x":3}\n'), RecordOptions("demo", tmp_path, "jsonl", overwrite=True))
    assert list(Session.open(replaced).records())[0]["x"] == 3


def test_empty_explicit_format_and_unicode(tmp_path: Path) -> None:
    path = record_stream(io.StringIO(""), RecordOptions("測定", tmp_path, "jsonl"))
    assert Session.open(path).manifest["record_count"] == 0


def test_large_stream(tmp_path: Path) -> None:
    stream = io.StringIO("".join(f'{{"x":{i}}}\n' for i in range(10_000)))
    session = Session.open(record_stream(stream, RecordOptions("large", tmp_path, "jsonl")))
    assert session.manifest["valid_record_count"] == 10_000


def test_hash_tamper(tmp_path: Path) -> None:
    path = record_stream(io.StringIO('{"x":1}\n'), RecordOptions("demo", tmp_path, "jsonl"))
    (path / "raw.log").write_text("changed", encoding="utf-8")
    assert Session.open(path).verify() == ["hash mismatch: raw.log"]

