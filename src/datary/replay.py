"""Session replay with real or virtual timing."""

from __future__ import annotations

import csv
import json
import math
import time
from typing import IO, Callable, Optional

from datary.sessions import Session
from datary.utils import csv_safe_cell, temporal_number


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
    if speed <= 0 or not math.isfinite(speed):
        raise ValueError("speed must be finite and positive")
    time_field = session.manifest.get("time_field")
    previous: Optional[float] = None
    fields = sorted(session.manifest.get("fields", {}))
    writer = csv.writer(output, lineterminator="\n") if output_format == "csv" else None
    if output_format == "csv":
        assert writer is not None
        writer.writerow([csv_safe_cell(field) for field in fields])
    for record in session.records():
        current = temporal_number(record.get(time_field)) if time_field else None
        if not no_timing and not virtual and current is not None and previous is not None:
            delay = max(0.0, (current - previous) / speed)
            if delay:
                sleep(delay)
        previous = current if current is not None else previous
        if output_format == "jsonl":
            output.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        elif output_format == "csv":
            assert writer is not None
            writer.writerow([csv_safe_cell(record.get(field)) for field in fields])
        else:
            raise ValueError("replay format must be jsonl or csv")
        output.flush()
