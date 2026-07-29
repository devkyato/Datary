from pathlib import Path

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
