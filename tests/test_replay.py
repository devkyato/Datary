import io
from pathlib import Path

import pytest

from datary.models import RecordOptions
from datary.recorder import record_stream
from datary.replay import replay_session
from datary.sessions import Session


def test_replay_virtual_and_timing(tmp_path: Path) -> None:
    session = Session.open(
        record_stream(io.StringIO('{"t":0}\n{"t":2}\n'), RecordOptions("a", tmp_path, "jsonl", "t"))
    )
    output = io.StringIO()
    sleeps: list[float] = []
    replay_session(session, output, speed=2, sleep=sleeps.append)
    assert sleeps == [1.0]
    output = io.StringIO()
    replay_session(session, output, virtual=True)
    assert len(output.getvalue().splitlines()) == 2


def test_csv_replay_quotes_and_neutralizes_formulas(tmp_path: Path) -> None:
    session = Session.open(
        record_stream(
            io.StringIO('{"text":"a,b","formula":"=2+2"}\n'),
            RecordOptions("csv", tmp_path, "jsonl"),
        )
    )
    output = io.StringIO()
    replay_session(session, output, output_format="csv", no_timing=True)
    assert '"a,b"' in output.getvalue()
    assert "'=2+2" in output.getvalue()


def test_replay_rejects_nonfinite_speed(tmp_path: Path) -> None:
    session = Session.open(
        record_stream(io.StringIO('{"x":1}\n'), RecordOptions("speed", tmp_path, "jsonl"))
    )
    with pytest.raises(ValueError, match="finite"):
        replay_session(session, io.StringIO(), speed=float("nan"))
