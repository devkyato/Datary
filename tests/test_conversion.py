import json
import os
from pathlib import Path

import pytest

from datary.conversion import convert_source


def test_conversion_streams_multiline_csv_and_writes_sidecar(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    source.write_text('name,value\n"two\nlines",1\nbroken\n', encoding="utf-8")
    output = tmp_path / "output.jsonl"
    valid, invalid = convert_source(source, output, "jsonl", "csv")
    assert (valid, invalid) == (1, 1)
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "name": f"two{os.linesep}lines",
        "value": 1,
    }
    sidecar = json.loads(output.with_suffix(".jsonl.invalid.json").read_text(encoding="utf-8"))
    assert sidecar["invalid_record_count"] == 1


def test_conversion_never_silently_overwrites(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    source.write_text('{"x":1}\n', encoding="utf-8")
    output = tmp_path / "output.csv"
    output.write_text("keep\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        convert_source(source, output, "csv", "jsonl")
    assert output.read_text(encoding="utf-8") == "keep\n"


def test_clean_conversion_replaces_stale_invalid_count(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    source.write_text('{"x":1}\n', encoding="utf-8")
    output = tmp_path / "output.csv"
    sidecar = output.with_suffix(".csv.invalid.json")
    sidecar.write_text('{"invalid_record_count": 99}\n', encoding="utf-8")
    convert_source(source, output, "csv", "jsonl")
    assert json.loads(sidecar.read_text(encoding="utf-8"))["invalid_record_count"] == 0
