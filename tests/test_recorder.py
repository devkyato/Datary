import io
import json
import os
import tracemalloc
from collections.abc import Iterator
from pathlib import Path
from typing import IO, cast

import pytest

import datary.recorder
from datary.models import RecordOptions
from datary.recorder import record_stream
from datary.sessions import Session


def test_record_session_and_integrity(tmp_path: Path) -> None:
    path = record_stream(
        io.StringIO('{"t":0,"x":1}\nbad\n{"t":1,"x":2}\n'),
        RecordOptions("demo", tmp_path, "jsonl", "t"),
    )
    session = Session.open(path)
    assert session.manifest["valid_record_count"] == 2
    assert session.manifest["invalid_record_count"] == 1
    assert session.manifest["working_directory"] == "<redacted>"
    assert session.verify() == []
    assert (path / "raw.log").read_text(encoding="utf-8").endswith('{"t":1,"x":2}\n')
    assert b"\r\n" not in (path / "data.csv").read_bytes()


def test_duplicate_names_and_overwrite(tmp_path: Path) -> None:
    first = record_stream(io.StringIO('{"x":1}\n'), RecordOptions("demo", tmp_path, "jsonl"))
    second = record_stream(io.StringIO('{"x":2}\n'), RecordOptions("demo", tmp_path, "jsonl"))
    assert first.name == "demo"
    assert second.name == "demo-2"
    replaced = record_stream(
        io.StringIO('{"x":3}\n'), RecordOptions("demo", tmp_path, "jsonl", overwrite=True)
    )
    assert list(Session.open(replaced).records())[0]["x"] == 3


def test_empty_explicit_format_and_unicode(tmp_path: Path) -> None:
    path = record_stream(io.StringIO(""), RecordOptions("測定", tmp_path, "jsonl"))
    assert Session.open(path).manifest["record_count"] == 0


def test_large_stream_has_a_bounded_python_heap(tmp_path: Path) -> None:
    class GeneratedStream:
        def __init__(self, count: int) -> None:
            self.index = 0
            self.count = count

        def readline(self, _size: int = -1) -> str:
            if self.index >= self.count:
                return ""
            line = f'{{"x":{self.index}}}\n'
            self.index += 1
            return line

    count = 50_000
    stream = cast(IO[str], GeneratedStream(count))
    tracemalloc.start()
    tracemalloc.reset_peak()
    session = Session.open(record_stream(stream, RecordOptions("large", tmp_path, "jsonl")))
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert session.manifest["valid_record_count"] == count
    # This catches accidental record/error list accumulation. It is a Python
    # heap ceiling, not an operating-system RSS guarantee.
    assert peak < 32 * 1024 * 1024


def test_hash_tamper(tmp_path: Path) -> None:
    path = record_stream(io.StringIO('{"x":1}\n'), RecordOptions("demo", tmp_path, "jsonl"))
    (path / "raw.log").write_text("changed", encoding="utf-8")
    assert Session.open(path).verify() == ["hash mismatch: raw.log"]


def test_nonfinite_input_is_preserved_as_invalid(tmp_path: Path) -> None:
    path = record_stream(
        io.StringIO('{"x":NaN}\n{"x":2}\n'),
        RecordOptions("nonfinite", tmp_path, "jsonl"),
    )
    session = Session.open(path)
    assert session.manifest["valid_record_count"] == 1
    assert session.manifest["invalid_record_count"] == 1
    assert "non-finite" in (path / "invalid.jsonl").read_text(encoding="utf-8")
    assert "invalid.jsonl" in session.manifest["hashes"]
    assert not (path / ".analysis.sqlite3").exists()


def test_failed_overwrite_keeps_original_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = record_stream(io.StringIO('{"x":1}\n'), RecordOptions("demo", tmp_path, "jsonl"))

    def fail_publish(*_args: object) -> None:
        raise OSError("simulated publish failure")

    monkeypatch.setattr(datary.recorder, "_publish", fail_publish)
    with pytest.raises(OSError, match="simulated"):
        record_stream(
            io.StringIO('{"x":2}\n'),
            RecordOptions("demo", tmp_path, "jsonl", overwrite=True),
        )
    assert list(Session.open(path).records()) == [{"x": 1}]


def test_publish_restores_backup_when_final_rename_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    final = tmp_path / "final"
    staging = tmp_path / "staging"
    backup = tmp_path / "backup"
    final.mkdir()
    staging.mkdir()
    (final / "old").write_text("old", encoding="utf-8")
    (staging / "new").write_text("new", encoding="utf-8")
    real_replace = os.replace

    def fail_new(source: Path, destination: Path) -> None:
        if source == staging and destination == final:
            raise OSError("simulated final rename failure")
        real_replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_new)
    with pytest.raises(OSError, match="final rename"):
        datary.recorder._publish(staging, final, backup, True)
    assert (final / "old").read_text(encoding="utf-8") == "old"
    assert not backup.exists()


def test_manifest_and_invalid_artifact_integrity(tmp_path: Path) -> None:
    path = record_stream(io.StringIO("bad\n"), RecordOptions("demo", tmp_path, "jsonl"))
    (path / "invalid.jsonl").write_text("changed\n", encoding="utf-8")
    assert "hash mismatch: invalid.jsonl" in Session.open(path).verify()
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    manifest["record_count"] = 99
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="inconsistent"):
        Session.open(path)

    other = record_stream(io.StringIO('{"x":1}\n'), RecordOptions("manifest", tmp_path, "jsonl"))
    other_manifest = json.loads((other / "manifest.json").read_text(encoding="utf-8"))
    other_manifest["original_command"] = "changed"
    (other / "manifest.json").write_text(json.dumps(other_manifest), encoding="utf-8")
    assert "hash mismatch: manifest.json" in Session.open(other).verify()


def test_interrupted_auto_detection_finishes_a_session(tmp_path: Path) -> None:
    class InterruptedStream:
        def readline(self, size: int = -1) -> str:
            raise KeyboardInterrupt

        def __iter__(self) -> Iterator[str]:
            return iter(())

    stream = cast(IO[str], InterruptedStream())
    path = record_stream(stream, RecordOptions("stopped", tmp_path))
    manifest = Session.open(path).manifest
    assert manifest["interrupted"] is True
    assert manifest["record_count"] == 0


def test_engineering_field_roles_are_recorded_and_analysed(tmp_path: Path) -> None:
    source = "".join(
        json.dumps(
            {
                "t": index / 10,
                "target": 1,
                "response": 1 - 2.71828 ** (-index / 10),
            }
        )
        + "\n"
        for index in range(31)
    )
    path = record_stream(
        io.StringIO(source),
        RecordOptions(
            "control",
            tmp_path,
            "jsonl",
            time_field="t",
            target_field="target",
            response_field="response",
        ),
    )
    session = Session.open(path)
    assert session.manifest["field_roles"]["target"] == "target"
    metrics = json.loads((path / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["control"]["mean_absolute_error"] > 0


def test_line_limit_rejects_before_session_publication(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="line exceeds"):
        record_stream(
            io.StringIO('{"x":"' + ("a" * 100) + '"}\n'),
            RecordOptions("limited", tmp_path, "jsonl", max_line_bytes=32),
        )
    assert not (tmp_path / "limited").exists()


def test_unknown_field_roles_and_units_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="time field"):
        record_stream(
            io.StringIO('{"x":1}\n'),
            RecordOptions("role", tmp_path, "jsonl", time_field="missing"),
        )
    with pytest.raises(ValueError, match="unknown fields"):
        record_stream(
            io.StringIO('{"x":1}\n'),
            RecordOptions("unit", tmp_path, "jsonl", units={"missing": "m"}),
        )


def test_parser_failure_still_drains_raw_input(tmp_path: Path) -> None:
    source = '[{"x":1}, broken]\nthis tail must remain\n'
    path = record_stream(io.StringIO(source), RecordOptions("raw-tail", tmp_path, "json"))
    assert (path / "raw.log").read_text(encoding="utf-8") == source
    assert Session.open(path).manifest["invalid_record_count"] == 1
