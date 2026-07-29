"""Safe, streaming format conversion."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from datary.analysis_store import AnalysisStore
from datary.inspection import iter_source
from datary.utils import atomic_json, csv_safe_cell


def convert_source(
    source: Path,
    output: Path,
    to_format: str,
    input_format: Optional[str] = None,
    overwrite: bool = False,
) -> tuple[int, int]:
    if to_format not in {"csv", "jsonl"}:
        raise ValueError("conversion target must be csv or jsonl")
    if output.exists() and not overwrite:
        raise FileExistsError(output)
    if output.is_symlink():
        raise ValueError("conversion output may not be a symbolic link")
    output.parent.mkdir(parents=True, exist_ok=True)
    iterator, known_invalid, _, _, _ = iter_source(source, input_format)
    output_descriptor, temporary_output_name = tempfile.mkstemp(
        prefix=f".{output.name}.converting-",
        suffix=output.suffix,
        dir=str(output.parent),
    )
    temporary_output = Path(temporary_output_name)
    valid = 0
    invalid = known_invalid
    fd, database_name = tempfile.mkstemp(prefix="datary-convert-", suffix=".sqlite3")
    os.close(fd)
    database = Path(database_name)
    try:
        with (
            os.fdopen(
                output_descriptor,
                "w",
                encoding="utf-8",
                newline="\n" if to_format == "jsonl" else "",
            ) as stream,
            AnalysisStore(database) as analysis,
        ):
            for record in iterator:
                if record is None:
                    invalid += 1
                    continue
                valid += 1
                if to_format == "jsonl":
                    stream.write(
                        json.dumps(
                            record,
                            ensure_ascii=False,
                            allow_nan=False,
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
                else:
                    analysis.add(record)
            if to_format == "csv":
                analysis.finish()
                fields = analysis.fields
                writer = csv.DictWriter(stream, fieldnames=fields)
                csv.writer(stream).writerow([csv_safe_cell(field) for field in fields])
                for record in analysis.records():
                    writer.writerow({field: csv_safe_cell(record.get(field)) for field in fields})
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_output, output)
        atomic_json(
            output.with_suffix(output.suffix + ".invalid.json"),
            {
                "invalid_record_count": invalid,
                "source": str(source),
                "explanation": (
                    "Malformed source records were omitted from the converted data; "
                    "inspect the original source or a Datary session invalid.jsonl "
                    "for record-level evidence."
                ),
            },
        )
        return valid, invalid
    finally:
        database.unlink(missing_ok=True)
        temporary_output.unlink(missing_ok=True)
