import random
import string
from collections.abc import Iterator
from pathlib import Path

import pytest

from datary.parsers import parse_lines


@pytest.mark.parametrize(
    ("kind", "lines", "expected"),
    [
        ("csv", ["a,b\n", "1,two\n"], {"a": 1, "b": "two"}),
        ("tsv", ["a\tb\n", "1\t2\n"], {"a": 1, "b": 2}),
        ("json", ['[{"a":1}]'], {"a": 1}),
        ("jsonl", ['{"a":1}\n'], {"a": 1}),
        ("whitespace", ["1 2\n"], {"field_1": 1, "field_2": 2}),
        ("keyvalue", ["a=1 b=two\n"], {"a": 1, "b": "two"}),
        ("stream", ["1,2\n"], {"field_1": 1, "field_2": 2}),
    ],
)
def test_formats(kind: str, lines: list[str], expected: dict[str, object]) -> None:
    assert list(parse_lines(lines, kind))[0].record == expected


def test_malformed_and_limits() -> None:
    assert list(parse_lines(["nope\n"], "jsonl"))[0].error
    assert list(parse_lines(['{"a":1,"b":2}\n'], "jsonl", 1))[0].error


def test_csv_record_length_change() -> None:
    results = list(parse_lines(["a,b\n", "1\n"], "csv"))
    assert results[0].error and "expected 2" in results[0].error


def test_multiline_csv_and_bom() -> None:
    results = list(parse_lines(["\ufeffa,b\n", '1,"two\n', 'lines"\n'], "csv"))
    assert len(results) == 1
    assert results[0].record == {"a": 1, "b": "two\nlines"}


def test_bom_jsonl_conservative_scalars_and_nonfinite() -> None:
    assert list(parse_lines(['\ufeff{"a":1}\n'], "jsonl"))[0].record == {"a": 1}
    record = list(parse_lines(["00123,NA,1e3\n"], "stream"))[0].record
    assert record == {"field_1": "00123", "field_2": "NA", "field_3": 1000.0}
    assert "non-finite" in (list(parse_lines(['{"a":NaN}\n'], "jsonl"))[0].error or "")


def test_json_array_is_incremental() -> None:
    consumed: list[int] = []

    def chunks() -> Iterator[str]:
        consumed.append(1)
        yield '[{"a":1},'
        consumed.append(2)
        yield '{"a":2}]'

    parsed = parse_lines(chunks(), "json")
    assert next(parsed).record == {"a": 1}
    assert consumed == [1]
    assert [item.record for item in parsed] == [{"a": 2}]


def test_duplicate_json_keys_are_rejected() -> None:
    result = list(parse_lines(['{"a":1,"a":2}\n'], "jsonl"))[0]
    assert result.record is None
    assert "duplicate JSON object key" in (result.error or "")


def test_deterministic_hostile_text_corpus_never_executes_or_crashes(tmp_path: Path) -> None:
    rng = random.Random(20260729)
    alphabet = string.printable + "\x00\x1b\u202e\u2603"
    corpus = [
        "".join(rng.choice(alphabet) for _ in range(rng.randrange(0, 160))) + "\n"
        for _ in range(250)
    ]
    marker = tmp_path / "must-not-exist"
    payloads = corpus + [
        f'__import__("pathlib").Path("{marker.as_posix()}").touch()\n',
        "=cmd|' /C calc'!A0\n",
        '{"__class__":{"__mro__":"ignored"}}\n',
    ]
    for kind in ("csv", "tsv", "jsonl", "whitespace", "keyvalue", "stream"):
        list(parse_lines(payloads, kind))
    assert not marker.exists()
