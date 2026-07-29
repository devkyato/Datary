"""Session replay with real or virtual timing."""

from __future__ import annotations

import json
import time
from typing import IO, Callable, Optional

from datary.sessions import Session
from datary.utils import finite_number


def replay_session(
    session: Session,
    output: IO[str],
    *,
    speed: float = 1.0,
    no_timing: bool = False,
    virtual: bool = False,
    output_format: str = "jsonl",
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    if speed <= 0:
        raise ValueError("speed must be positive")
    time_field = session.manifest.get("time_field")
    previous: Optional[float] = None
    fields = sorted(session.manifest.get("fields", {}))
    if output_format == "csv":
        output.write(",".join(fields) + "\n")
    for record in session.records():
        current = finite_number(record.get(time_field)) if time_field else None
        if not no_timing and not virtual and current is not None and previous is not None:
            delay = max(0.0, (current - previous) / speed)
            if delay:
                sleep(delay)
        previous = current if current is not None else previous
        if output_format == "jsonl":
            output.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        elif output_format == "csv":
            output.write(",".join(_csv_cell(record.get(field)) for field in fields) + "\n")
        else:
            raise ValueError("replay format must be jsonl or csv")
        output.flush()


def _csv_cell(value: object) -> str:
    import csv
    import io

    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="").writerow([value])
    return buffer.getvalue()

