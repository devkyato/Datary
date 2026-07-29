import pytest

from datary.formats import AmbiguousFormatError, detect_format


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('[{"x": 1}]', "json"),
        ('{"x":1}\n{"x":2}\n', "jsonl"),
        ("a,b\n1,2\n", "csv"),
        ("a\tb\n1\t2\n", "tsv"),
        ("x=1 y=two\n", "keyvalue"),
        ("1 2\n3 4\n", "whitespace"),
    ],
)
def test_detection(text: str, expected: str) -> None:
    assert detect_format(text)[0] == expected


@pytest.mark.parametrize("text", ["", "1,2\n3,4\n", "hello"])
def test_ambiguous(text: str) -> None:
    with pytest.raises(AmbiguousFormatError):
        detect_format(text)

