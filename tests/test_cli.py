import importlib
from pathlib import Path

import pytest

from datary.cli import main, parser


def test_version_and_help(capsys: object) -> None:
    try:
        main(["--version"])
    except SystemExit as error:
        assert error.code == 0


def test_generate_cli(tmp_path: Path) -> None:
    output = tmp_path / "data.jsonl"
    assert main(["generate", "sine", "--duration", "1", "--output", str(output)]) == 0
    assert output.exists()


def test_cli_bad_source() -> None:
    assert main(["inspect", "does-not-exist"]) == 2


def test_quality_field_options_are_repeatable() -> None:
    arguments = parser().parse_args(
        [
            "inspect",
            "session",
            "--monotonic-field",
            "distance",
            "--counter-field",
            "packets",
        ]
    )
    assert arguments.monotonic_field == ["distance"]
    assert arguments.counter_field == ["packets"]


def test_overwrite_conflict_mentions_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "data.jsonl"
    assert main(["generate", "sine", "--duration", "1", "--output", str(output)]) == 0
    assert main(["generate", "sine", "--duration", "1", "--output", str(output)]) == 2
    message = capsys.readouterr().err
    assert "path already exists" in message
    assert "--overwrite" in message


def test_compare_requires_two_sources(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["compare", "only-one"]) == 2
    assert "at least two sources" in capsys.readouterr().err


def test_doctor_treats_plotting_as_optional(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(_name: str) -> object:
        raise ImportError

    monkeypatch.setattr(importlib, "import_module", unavailable)
    assert main(["--workspace", str(tmp_path), "doctor"]) == 0
    assert "OPTIONAL-MISSING  optional_plotting_available" in capsys.readouterr().out
