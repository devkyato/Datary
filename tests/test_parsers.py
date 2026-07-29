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

