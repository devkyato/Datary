"""Bounded-memory, line-streaming session recorder."""

from __future__ import annotations

import csv
import json
import os
import shutil
from pathlib import Path
from typing import IO, Any, Dict, Iterable, List

from datary import __version__
from datary.config import SESSION_FORMAT_VERSION
from datary.formats import detect_format
from datary.metrics import summarize_records
from datary.models import Record, RecordOptions
from datary.parsers import parse_lines
from datary.quality import analyze_quality
from datary.utils import atomic_json, infer_type, safe_name, sha256_file, utc_now


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
    final_path = _session_path(options)
    staging = final_path.with_name(f".{final_path.name}.recording-{os.getpid()}")
    if staging.exists():
        raise ValueError(f"staging path already exists: {staging}")
    if final_path.exists():
        if not options.overwrite:
            raise FileExistsError(final_path)
        if final_path.is_symlink() or not final_path.is_dir():
            raise ValueError("refusing to overwrite unsafe session path")
        shutil.rmtree(final_path)
    staging.mkdir(parents=True)
    (staging / "plots").mkdir()
    (staging / "reports").mkdir()
    started = utc_now()
    raw_path = staging / "raw.log"
    records_path = staging / "records.jsonl"
    invalid_path = staging / "invalid.jsonl"
    records: List[Record] = []
    errors: List[Dict[str, Any]] = []
    interrupted = False
    input_format = options.input_format
    try:
        with raw_path.open("w", encoding="utf-8", newline="") as raw:
            sample_lines: List[str] = []
            if input_format is None:
                while sum(len(item.encode("utf-8")) for item in sample_lines) < 262_144:
                    line = stream.readline()
                    if not line:
                        break
                    _validate_line(line, options.max_line_bytes)
                    raw.write(line)
                    sample_lines.append(line)
                    if len(sample_lines) >= 20:
                        break
                input_format, _ = detect_format("".join(sample_lines))
            with records_path.open("w", encoding="utf-8", newline="\n") as clean, invalid_path.open(
                "w", encoding="utf-8", newline="\n"
            ) as invalid:
                line_number = 0

                def source() -> Iterable[str]:
                    nonlocal line_number, interrupted
                    for item in sample_lines:
                        line_number += 1
                        yield item
                    try:
                        for item in stream:
                            _validate_line(item, options.max_line_bytes)
                            raw.write(item)
                            line_number += 1
                            yield item
                    except KeyboardInterrupt:
                        interrupted = True

                for result in parse_lines(source(), input_format, options.max_fields):
                    if result.record is not None:
                        records.append(result.record)
                        clean.write(json.dumps(result.record, ensure_ascii=False, allow_nan=False) + "\n")
                    else:
                        error = {"record": len(records) + len(errors) + 1, "reason": result.error}
                        errors.append(error)
                        invalid.write(json.dumps(error, ensure_ascii=False) + "\n")
                    if (len(records) + len(errors)) % 1000 == 0:
                        raw.flush()
                        clean.flush()
                        invalid.flush()
        _write_csv(staging / "data.csv", records)
        metrics = summarize_records(records, options.time_field)
        quality = [finding.to_dict() for finding in analyze_quality(records, options.time_field)]
        atomic_json(staging / "metrics.json", metrics)
        atomic_json(staging / "quality.json", {"findings": quality})
        (staging / "notes.md").write_text("# Notes\n\n", encoding="utf-8")
        fields = {
            key: infer_type(record.get(key) for record in records)
            for key in sorted({key for record in records for key in record})
        }
        ended = utc_now()
        hashes = {
            name: sha256_file(staging / name)
            for name in ("raw.log", "records.jsonl", "data.csv", "metrics.json", "quality.json")
        }
        session_name = final_path.name
        manifest = {
            "datary_version": __version__,
            "session_format_version": SESSION_FORMAT_VERSION,
            "session_name": session_name,
            "started_at": started,
            "ended_at": ended,
            "original_command": options.command,
            "working_directory": str(Path.cwd().resolve()) if options.include_path else "<redacted>",
            "parameters": options.parameters,
            "input_format": input_format,
            "fields": fields,
            "record_count": len(records) + len(errors),
            "valid_record_count": len(records),
            "invalid_record_count": len(errors),
            "time_field": options.time_field,
            "sampling": metrics.get("timing", {}),
            "units": options.units,
            "parser_warnings": [item["reason"] for item in errors[:100]],
            "interrupted": interrupted,
            "hashes": hashes,
            "commands": {
                "inspect": f"datary inspect {session_name}",
                "compare": f"datary compare {session_name} OTHER",
                "replay": f"datary replay {session_name}",
                "report": f"datary report {session_name}",
            },
        }
        atomic_json(staging / "manifest.json", manifest)
        os.replace(staging, final_path)
        return final_path
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise


def _validate_line(line: str, maximum: int) -> None:
    if len(line.encode("utf-8")) > maximum:
        raise ValueError(f"input line exceeds byte limit ({maximum})")


def _write_csv(path: Path, records: List[Record]) -> None:
    fields = sorted({key for record in records for key in record})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({key: _cell(record.get(key)) for key in fields})


def _cell(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return value
