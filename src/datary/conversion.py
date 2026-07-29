"""Safe format conversion."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Optional

from datary.inspection import load_source


def convert_source(
    source: Path, output: Path, to_format: str, input_format: Optional[str] = None, overwrite: bool = False
) -> tuple[int, int]:
    if output.exists() and not overwrite:
        raise FileExistsError(output)
    records, invalid, _, _, _ = load_source(source, input_format)
    output.parent.mkdir(parents=True, exist_ok=True)
    if to_format == "jsonl":
        with output.open("w", encoding="utf-8", newline="\n") as stream:
            for record in records:
                stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
    elif to_format == "csv":
        fields = sorted({key for record in records for key in record})
        with output.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for record in records:
                writer.writerow({key: _cell(record.get(key)) for key in fields})
    else:
        raise ValueError("conversion target must be csv or jsonl")
    if invalid:
        sidecar = output.with_suffix(output.suffix + ".invalid.json")
        sidecar.write_text(
            json.dumps({"invalid_record_count": invalid, "source": str(source)}, indent=2) + "\n",
            encoding="utf-8",
        )
    return len(records), invalid


def _cell(value: Any) -> Any:
    return json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (list, dict)) else value

