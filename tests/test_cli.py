from pathlib import Path

from datary.cli import main


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

