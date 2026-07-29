import io
from pathlib import Path

from datary.models import RecordOptions
from datary.recorder import record_stream
from datary.replay import replay_session
from datary.sessions import Session


def test_replay_virtual_and_timing(tmp_path: Path) -> None:
    session = Session.open(record_stream(io.StringIO('{"t":0}\n{"t":2}\n'), RecordOptions("a", tmp_path, "jsonl", "t")))
    output = io.StringIO()
    sleeps: list[float] = []
    replay_session(session, output, speed=2, sleep=sleeps.append)
    assert sleeps == [1.0]
    output = io.StringIO()
    replay_session(session, output, virtual=True)
    assert len(output.getvalue().splitlines()) == 2

