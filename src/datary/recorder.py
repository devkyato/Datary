"""Bounded-memory, line-streaming session recorder."""

from __future__ import annotations

import csv
import json
import os
import shutil
from pathlib import Path
from typing import IO, Any, Dict, Iterable, List

from datary import __version__
from datary.analysis_store import AnalysisStore
from datary.config import MAX_AUTO_DETECT_BYTES, SESSION_FORMAT_VERSION
from datary.formats import SUPPORTED_FORMATS, AmbiguousFormatError, detect_format
from datary.models import RecordOptions
from datary.parsers import parse_lines
from datary.utils import (
    atomic_json,
    atomic_text,
    bounded_text_lines,
    csv_safe_cell,
    safe_name,
    sha256_file,
    utc_now,
)


def _session_path(options: RecordOptions) -> Path:
    root = options.workspace.resolve()
    root.mkdir(parents=True, exist_ok=True)
    name = safe_name(options.name)
    base = root / name
    if not base.exists() or options.overwrite:
        return base
    index = 2
    while (root / f"{name}-{index}").exists():
        index += 1
    return root / f"{name}-{index}"


def record_stream(stream: IO[str], options: RecordOptions) -> Path:
    """Capture a stream and publish a complete session with recoverable overwrite."""

    _validate_options(options)
    final_path = _session_path(options)
    staging = final_path.with_name(f".{final_path.name}.recording-{os.getpid()}")
    backup = final_path.with_name(f".{final_path.name}.backup-{os.getpid()}")
    if staging.exists() or backup.exists():
        raise ValueError("a recorder staging or backup path already exists")
    if final_path.exists():
        if not options.overwrite:
            raise FileExistsError(final_path)
        if final_path.is_symlink() or not final_path.is_dir():
            raise ValueError("refusing to overwrite unsafe session path")
    staging.mkdir(parents=True)
    (staging / "plots").mkdir()
    (staging / "reports").mkdir()
    started = utc_now()
    raw_path = staging / "raw.log"
    records_path = staging / "records.jsonl"
    invalid_path = staging / "invalid.jsonl"
    analysis_path = staging / ".analysis.sqlite3"
    interrupted = False
    input_format = options.input_format
    valid_count = 0
    invalid_count = 0
    parser_warnings: List[str] = []
    published = False
    try:
        with (
            AnalysisStore(analysis_path, options.max_fields) as analysis,
            raw_path.open("w", encoding="utf-8", newline="") as raw,
            records_path.open("w", encoding="utf-8", newline="\n") as clean,
            invalid_path.open("w", encoding="utf-8", newline="\n") as invalid,
        ):
            sample_lines: List[str] = []
            bounded_input = iter(bounded_text_lines(stream, options.max_line_bytes))
            if input_format is None:
                try:
                    sample_bytes = 0
                    while sample_bytes < MAX_AUTO_DETECT_BYTES and len(sample_lines) < 20:
                        try:
                            line = next(bounded_input)
                        except StopIteration:
                            break
                        raw.write(line)
                        sample_lines.append(line)
                        sample_bytes += len(line.encode("utf-8"))
                except KeyboardInterrupt:
                    interrupted = True
                try:
                    input_format, detection_warnings = detect_format("".join(sample_lines))
                    parser_warnings.extend(detection_warnings)
                except AmbiguousFormatError:
                    if not interrupted:
                        raise
                    input_format = "jsonl"
                    parser_warnings.append(
                        "recording was interrupted before format detection completed; "
                        "captured input was conservatively parsed as JSON Lines"
                    )

            def source() -> Iterable[str]:
                nonlocal interrupted
                yield from sample_lines
                if interrupted:
                    return
                try:
                    for item in bounded_input:
                        raw.write(item)
                        yield item
                except KeyboardInterrupt:
                    interrupted = True

            try:
                for result in parse_lines(source(), input_format, options.max_fields):
                    if result.record is not None:
                        analysis.add(result.record)
                        clean.write(
                            json.dumps(
                                result.record,
                                ensure_ascii=False,
                                allow_nan=False,
                                separators=(",", ":"),
                            )
                            + "\n"
                        )
                        valid_count += 1
                    else:
                        invalid_count += 1
                        reason = result.error or "unknown parser error"
                        error = {
                            "record": valid_count + invalid_count,
                            "reason": reason,
                        }
                        if len(parser_warnings) < 100:
                            parser_warnings.append(reason)
                        invalid.write(json.dumps(error, ensure_ascii=False) + "\n")
                    if (valid_count + invalid_count) % 1000 == 0:
                        raw.flush()
                        clean.flush()
                        invalid.flush()
            except KeyboardInterrupt:
                interrupted = True
            if not interrupted:
                try:
                    for unparsed_line in bounded_input:
                        raw.write(unparsed_line)
                except KeyboardInterrupt:
                    interrupted = True
            raw.flush()
            clean.flush()
            invalid.flush()
            os.fsync(raw.fileno())
            os.fsync(clean.fileno())
            os.fsync(invalid.fileno())
            analysis.finish()
            fields = analysis.field_definitions()
            requested_roles = {
                "time": options.time_field,
                "target": options.target_field,
                "response": options.response_field,
                "sequence": options.sequence_field,
                "latency": options.latency_field,
                "bytes": options.bytes_field,
            }
            for role, field in requested_roles.items():
                if field is not None and field not in fields:
                    raise ValueError(f"{role} field {field!r} does not exist in valid records")
            unknown_units = sorted(set(options.units) - set(fields))
            if unknown_units:
                raise ValueError("units reference unknown fields: " + ", ".join(unknown_units))
            _write_csv(staging / "data.csv", analysis.records(), sorted(fields))
            metrics = analysis.metrics(options.time_field)
            if options.time_field and options.target_field and options.response_field:
                metrics["control"] = analysis.control_metrics(
                    options.time_field,
                    options.target_field,
                    options.response_field,
                )
            if options.sequence_field and options.latency_field:
                metrics["network"] = analysis.network_metrics(
                    options.sequence_field,
                    options.latency_field,
                    options.bytes_field,
                    options.time_field,
                )
            quality = [
                finding.to_dict()
                for finding in analysis.quality(
                    options.time_field,
                    sequence_field=options.sequence_field,
                )
            ]
        analysis_path.unlink(missing_ok=True)
        atomic_json(staging / "metrics.json", metrics)
        atomic_json(staging / "quality.json", {"findings": quality})
        atomic_text(staging / "notes.md", "# Notes\n\n")
        ended = utc_now()
        hashed_names = (
            "raw.log",
            "records.jsonl",
            "invalid.jsonl",
            "data.csv",
            "metrics.json",
            "quality.json",
            "notes.md",
        )
        hashes = {name: sha256_file(staging / name) for name in hashed_names}
        session_name = final_path.name
        manifest: Dict[str, Any] = {
            "datary_version": __version__,
            "session_format_version": SESSION_FORMAT_VERSION,
            "session_name": session_name,
            "started_at": started,
            "ended_at": ended,
            "original_command": options.command,
            "working_directory": (
                str(Path.cwd().resolve()) if options.include_path else "<redacted>"
            ),
            "parameters": options.parameters,
            "input_format": input_format,
            "parser_policy": "conservative-scalars-v1",
            "fields": fields,
            "record_count": valid_count + invalid_count,
            "valid_record_count": valid_count,
            "invalid_record_count": invalid_count,
            "time_field": options.time_field,
            "field_roles": {
                name: value
                for name, value in {
                    "target": options.target_field,
                    "response": options.response_field,
                    "sequence": options.sequence_field,
                    "latency": options.latency_field,
                    "bytes": options.bytes_field,
                }.items()
                if value is not None
            },
            "sampling": metrics.get("timing", {}),
            "units": options.units,
            "parser_warnings": parser_warnings,
            "interrupted": interrupted,
            "hashes": hashes,
            "integrity_scope": (
                "SHA-256 corruption detection for manifest and listed artifacts; "
                "not cryptographic authenticity"
            ),
            "commands": {
                "inspect": f"datary inspect {session_name}",
                "compare": f"datary compare {session_name} OTHER",
                "replay": f"datary replay {session_name}",
                "report": f"datary report {session_name}",
            },
            "command_context": (
                "Run from the session parent directory or set DATARY_WORKSPACE to that directory."
            ),
        }
        atomic_json(staging / "manifest.json", manifest)
        atomic_text(
            staging / "manifest.sha256",
            sha256_file(staging / "manifest.json") + "\n",
            encoding="ascii",
        )
        _publish(staging, final_path, backup, options.overwrite)
        published = True
        return final_path
    finally:
        if not published and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if backup.exists() and not final_path.exists():
            os.replace(backup, final_path)


def _publish(staging: Path, final: Path, backup: Path, overwrite: bool) -> None:
    moved_original = False
    try:
        if final.exists():
            if not overwrite:
                raise FileExistsError(final)
            os.replace(final, backup)
            moved_original = True
        os.replace(staging, final)
    except BaseException:
        if moved_original and backup.exists() and not final.exists():
            os.replace(backup, final)
        raise
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)


def _validate_options(options: RecordOptions) -> None:
    if options.input_format is not None and options.input_format not in SUPPORTED_FORMATS:
        raise ValueError(f"unsupported input format: {options.input_format}")
    if options.max_line_bytes <= 0:
        raise ValueError("max-line-bytes must be positive")
    if options.max_fields <= 0:
        raise ValueError("max-fields must be positive")
    if (options.target_field is None) != (options.response_field is None):
        raise ValueError("target-field and response-field must be supplied together")
    if options.target_field and not options.time_field:
        raise ValueError("control metrics require --time-field")
    if (options.sequence_field is None) != (options.latency_field is None):
        raise ValueError("sequence-field and latency-field must be supplied together")
    if options.bytes_field and not options.sequence_field:
        raise ValueError("bytes-field requires sequence and latency fields")
    for name, mapping in (("parameters", options.parameters), ("units", options.units)):
        if len(mapping) > 1000:
            raise ValueError(f"{name} exceed the 1000-entry limit")
        if any(
            not isinstance(key, str)
            or not isinstance(value, str)
            or len(key) > 120
            or len(value) > 4096
            for key, value in mapping.items()
        ):
            raise ValueError(f"{name} entries must be bounded strings")
    if options.command is not None and len(options.command) > 16_384:
        raise ValueError("original command exceeds 16384 characters")
    for field in (
        options.time_field,
        options.target_field,
        options.response_field,
        options.sequence_field,
        options.latency_field,
        options.bytes_field,
    ):
        if field is not None and (not field or len(field) > 1024):
            raise ValueError("field-role names must contain 1 to 1024 characters")


def _write_csv(path: Path, records: Iterable[Dict[str, Any]], fields: List[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        csv.writer(stream).writerow([csv_safe_cell(field) for field in fields])
        for record in records:
            writer.writerow({key: csv_safe_cell(record.get(key)) for key in fields})
        stream.flush()
        os.fsync(stream.fileno())
