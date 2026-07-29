"""Source inspection for sessions and ordinary files."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from datary.formats import detect_format
from datary.metrics import summarize_records
from datary.models import Inspection, Record
from datary.parsers import parse_lines
from datary.quality import analyze_quality
from datary.sessions import Session
from datary.utils import infer_type


def load_source(
    source: Union[str, Path, Session], input_format: Optional[str] = None
) -> tuple[List[Record], int, str, Dict[str, str], Optional[str]]:
    if isinstance(source, Session):
        return list(source.records()), int(source.manifest.get("invalid_record_count", 0)), str(source.manifest["input_format"]), dict(source.manifest.get("units", {})), source.manifest.get("time_field")
    path = Path(source)
    if path.is_dir():
        return load_source(Session.open(path), input_format)
    sample = path.read_text(encoding="utf-8")[:262_144]
    selected = input_format or detect_format(sample, path.name)[0]
    records: List[Record] = []
    invalid = 0
    with path.open("r", encoding="utf-8", newline="") as stream:
        for result in parse_lines(stream, selected):
            if result.record is None:
                invalid += 1
            else:
                records.append(result.record)
    return records, invalid, selected, {}, None


def inspect_source(
    source: Union[str, Path, Session],
    *,
    input_format: Optional[str] = None,
    time_field: Optional[str] = None,
    monotonic_fields: Optional[Sequence[str]] = None,
    counter_fields: Optional[Sequence[str]] = None,
) -> Inspection:
    records, invalid, selected, units, manifest_time = load_source(source, input_format)
    chosen_time = time_field or manifest_time
    fields = {
        field: infer_type(record.get(field) for record in records)
        for field in sorted({key for record in records for key in record})
    }
    metrics = summarize_records(records, chosen_time)
    return Inspection(
        source=str(source.path if isinstance(source, Session) else source),
        format=selected,
        record_count=len(records),
        invalid_count=invalid,
        fields=fields,
        metrics=metrics["numeric"],
        timing=metrics["timing"],
        quality=[
            finding.to_dict()
            for finding in analyze_quality(
                records,
                chosen_time,
                monotonic_fields=monotonic_fields,
                counter_fields=counter_fields,
            )
        ],
        units=units,
    )
