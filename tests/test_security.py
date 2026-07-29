import json
from pathlib import Path

import pytest

from datary.cli import main
from datary.models import RecordOptions
from datary.recorder import record_stream
from datary.sessions import Session
from datary.utils import csv_safe_cell, markdown_safe, safe_name, safe_output, terminal_safe


def test_path_traversal() -> None:
    with pytest.raises(ValueError):
        safe_name("../escape")
    with pytest.raises(ValueError):
        safe_output(Path.cwd(), Path("../escape"))


def test_malicious_manifest(tmp_path: Path) -> None:
    session = tmp_path / "bad"
    session.mkdir()
    (session / "records.jsonl").write_text("", encoding="utf-8")
    (session / "manifest.json").write_text(
        json.dumps(
            {
                "session_format_version": "1",
                "session_name": "bad",
                "record_count": 0,
                "hashes": {"../x": "bad"},
            }
        ),
        encoding="utf-8",
    )
    assert Session.open(session).verify()[0].startswith("unsafe hash path")


def test_symlink_session_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError):
        Session.open(link)


def test_csv_formula_neutralization() -> None:
    assert csv_safe_cell("=2+2") == "'=2+2"
    assert csv_safe_cell(" @SUM(A:A)") == "' @SUM(A:A)"
    assert csv_safe_cell("ordinary") == "ordinary"


def test_formula_like_csv_header_is_neutralized(tmp_path: Path) -> None:
    import io

    path = record_stream(
        io.StringIO('{"=formula":1}\n'),
        RecordOptions("formula", tmp_path, "jsonl"),
    )
    assert (path / "data.csv").read_text(encoding="utf-8").startswith("'=formula")


def test_terminal_and_markdown_control_content_is_escaped() -> None:
    assert "\x1b" not in terminal_safe("\x1b[31mred")
    assert terminal_safe("\x1b[31mred").startswith("\\x1b")
    assert "<script>" not in markdown_safe("<script>\n# heading")


def test_plot_field_cannot_escape_session(tmp_path: Path) -> None:
    import io

    session = record_stream(
        io.StringIO('{"../../escape":1}\n'),
        RecordOptions("plot-safe", tmp_path, "jsonl"),
    )
    assert (
        main(
            [
                "--workspace",
                str(tmp_path),
                "inspect",
                str(session),
                "--plot",
                "../../escape",
            ]
        )
        == 0
    )
    assert not (tmp_path / "escape.png").exists()
    assert list((session / "plots").glob("*.png"))
