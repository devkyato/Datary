"""Source inspection for sessions and ordinary local files."""

from __future__ import annotations

import codecs
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple, Union

from datary.analysis_store import AnalysisStore
from datary.config import LARGE_FILE_WARNING_BYTES, MAX_AUTO_DETECT_BYTES
from datary.formats import detect_format
from datary.models import Inspection, Record
from datary.parsers import parse_lines
from datary.sessions import Session
from datary.utils import bounded_text_lines


def load_source(
    source: Union[str, Path, Session],
    input_format: Optional[str] = None,
) -> Tuple[List[Record], int, str, Dict[str, str], Optional[str]]:
    """Load records for callers that explicitly need materialized data, such as plots."""

    iterator, invalid, selected, units, time_field = iter_source(source, input_format)
    records: List[Record] = []
    invalid_count = invalid
    for result in iterator:
        if result is None:
            invalid_count += 1
        else:
            records.append(result)
    return records, invalid_count, selected, units, time_field


def iter_source(
    source: Union[str, Path, Session],
    input_format: Optional[str] = None,
) -> Tuple[Iterator[Optional[Record]], int, str, Dict[str, str], Optional[str]]:
    """Return a lazy record iterator and source metadata."""

    if isinstance(source, Session):
        return (
            (record for record in source.records()),
            int(source.manifest.get("invalid_record_count", 0)),
            str(source.manifest["input_format"]),
            dict(source.manifest.get("units", {})),
            _optional_string(source.manifest.get("time_field")),
        )
    path = Path(source)
    if path.is_dir():
        return iter_source(Session.open(path), input_format)
    if not path.exists():
        return iter_source(Session.open(path), input_format)
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"source is missing or unsafe: {source}")
    if path.stat().st_size > LARGE_FILE_WARNING_BYTES:
        raise ValueError(
            f"source exceeds the default safety limit ({LARGE_FILE_WARNING_BYTES} bytes)"
        )
    with path.open("rb") as sample_stream:
        sample_bytes = sample_stream.read(MAX_AUTO_DETECT_BYTES)
    sample = codecs.getincrementaldecoder("utf-8-sig")().decode(sample_bytes, final=False)
    selected = input_format or detect_format(sample, path.name)[0]

    def records() -> Iterator[Optional[Record]]:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            for result in parse_lines(bounded_text_lines(stream, 1_048_576), selected):
                yield result.record

    return records(), 0, selected, {}, None


def inspect_source(
    source: Union[str, Path, Session],
    *,
    input_format: Optional[str] = None,
    time_field: Optional[str] = None,
    monotonic_fields: Optional[Sequence[str]] = None,
    counter_fields: Optional[Sequence[str]] = None,
    target_field: Optional[str] = None,
    response_field: Optional[str] = None,
    sequence_field: Optional[str] = None,
    latency_field: Optional[str] = None,
    bytes_field: Optional[str] = None,
) -> Inspection:
    if not isinstance(source, Session) and Path(source).is_dir():
        source = Session.open(Path(source))
    roles = dict(source.manifest.get("field_roles", {})) if isinstance(source, Session) else {}
    target_field = target_field or roles.get("target")
    response_field = response_field or roles.get("response")
    sequence_field = sequence_field or roles.get("sequence")
    latency_field = latency_field or roles.get("latency")
    bytes_field = bytes_field or roles.get("bytes")
    if (target_field is None) != (response_field is None):
        raise ValueError("target_field and response_field must be supplied together")
    if target_field and time_field is None and roles.get("time") is None:
        # A session time field is resolved below; ordinary files need it explicitly.
        if not isinstance(source, Session) or source.manifest.get("time_field") is None:
            raise ValueError("control metrics require a time field")
    if (sequence_field is None) != (latency_field is None):
        raise ValueError("sequence_field and latency_field must be supplied together")
    if bytes_field and not sequence_field:
        raise ValueError("bytes_field requires sequence and latency fields")
    iterator, known_invalid, selected, units, manifest_time = iter_source(source, input_format)
    fd, temporary_name = tempfile.mkstemp(prefix="datary-analysis-", suffix=".sqlite3")
    os.close(fd)
    temporary = Path(temporary_name)
    invalid = known_invalid
    try:
        with AnalysisStore(temporary) as analysis:
            for record in iterator:
                if record is None:
                    invalid += 1
                else:
                    analysis.add(record)
            analysis.finish()
            chosen_time = time_field or manifest_time
            metrics = analysis.metrics(chosen_time)
            fields = analysis.field_definitions()
            configured_fields = {
                "time": chosen_time,
                "target": target_field,
                "response": response_field,
                "sequence": sequence_field,
                "latency": latency_field,
                "bytes": bytes_field,
            }
            for role, field in configured_fields.items():
                if field is not None and field not in fields:
                    raise ValueError(f"{role} field {field!r} does not exist in valid records")
            for expectation, names in (
                ("monotonic", monotonic_fields or ()),
                ("counter", counter_fields or ()),
            ):
                missing = sorted(set(names) - set(fields))
                if missing:
                    raise ValueError(
                        f"{expectation} fields do not exist in valid records: " + ", ".join(missing)
                    )
            quality = [
                finding.to_dict()
                for finding in analysis.quality(
                    chosen_time,
                    sequence_field=sequence_field,
                    monotonic_fields=monotonic_fields,
                    counter_fields=counter_fields,
                )
            ]
            engineering: Dict[str, Any] = {}
            if chosen_time and target_field and response_field:
                control = analysis.control_metrics(chosen_time, target_field, response_field)
                if control:
                    engineering["control"] = control
            if sequence_field and latency_field:
                network = analysis.network_metrics(
                    sequence_field,
                    latency_field,
                    bytes_field,
                    chosen_time,
                )
                if network:
                    engineering["network"] = network
            count = analysis.count
        return Inspection(
            source=str(source.path if isinstance(source, Session) else source),
            format=selected,
            record_count=count,
            invalid_count=invalid,
            fields=fields,
            metrics=metrics["numeric"],
            timing=metrics["timing"],
            quality=quality,
            units=units,
            engineering=engineering,
        )
    finally:
        temporary.unlink(missing_ok=True)


def _optional_string(value: object) -> Optional[str]:
    return value if isinstance(value, str) else None
