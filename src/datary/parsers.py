"""Streaming parsers. Input is treated only as inert text."""

from __future__ import annotations

import csv
import json
import shlex
from typing import Any, Dict, Iterable, Iterator

from datary.models import ParseResult, Record


def scalar(value: str) -> Any:
    stripped = value.strip()
    if stripped == "":
        return None
    lowered = stripped.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "na", "n/a"}:
        return None
    try:
        return int(stripped)
    except ValueError:
        try:
            return float(stripped)
        except ValueError:
            return stripped


def parse_lines(lines: Iterable[str], input_format: str, max_fields: int = 1000) -> Iterator[ParseResult]:
    if input_format in {"csv", "tsv"}:
        yield from _delimited(lines, "\t" if input_format == "tsv" else ",", max_fields)
        return
    if input_format == "json":
        joined = "".join(lines)
        try:
            value = json.loads(joined)
            if not isinstance(value, list):
                yield ParseResult(None, "JSON input must be an array")
                return
            for item in value:
                yield _json_record(item, max_fields)
        except json.JSONDecodeError as error:
            yield ParseResult(None, f"invalid JSON: {error.msg}")
        return
    for line_number, line in enumerate(lines, 1):
        text = line.rstrip("\r\n")
        if not text.strip():
            yield ParseResult(None, f"line {line_number}: empty line")
            continue
        try:
            if input_format == "jsonl":
                result = _json_record(json.loads(text), max_fields)
            elif input_format == "keyvalue":
                pairs = shlex.split(text)
                record: Record = {}
                for pair in pairs:
                    if "=" not in pair:
                        raise ValueError(f"token lacks '=': {pair}")
                    key, value = pair.split("=", 1)
                    record[key] = scalar(value)
                result = _checked(record, max_fields)
            elif input_format == "whitespace":
                result = _checked(
                    {f"field_{index + 1}": scalar(value) for index, value in enumerate(text.split())},
                    max_fields,
                )
            elif input_format == "stream":
                result = _checked(
                    {
                        f"field_{index + 1}": scalar(value)
                        for index, value in enumerate(next(csv.reader([text])))
                    },
                    max_fields,
                )
            else:
                result = ParseResult(None, f"unsupported format: {input_format}")
        except (ValueError, json.JSONDecodeError, csv.Error) as error:
            result = ParseResult(None, f"line {line_number}: {error}")
        yield result


def _delimited(lines: Iterable[str], delimiter: str, max_fields: int) -> Iterator[ParseResult]:
    iterator = iter(lines)
    try:
        header = next(csv.reader([next(iterator)], delimiter=delimiter))
    except StopIteration:
        return
    except csv.Error as error:
        yield ParseResult(None, f"invalid header: {error}")
        return
    if not header or len(set(header)) != len(header) or any(not name.strip() for name in header):
        yield ParseResult(None, "header fields must be non-empty and unique")
        return
    for line_number, line in enumerate(iterator, 2):
        try:
            row = next(csv.reader([line], delimiter=delimiter))
            if len(row) != len(header):
                yield ParseResult(None, f"line {line_number}: expected {len(header)} fields, got {len(row)}")
            else:
                yield _checked(dict(zip(header, map(scalar, row))), max_fields)
        except csv.Error as error:
            yield ParseResult(None, f"line {line_number}: {error}")


def _json_record(value: Any, max_fields: int) -> ParseResult:
    if not isinstance(value, dict):
        return ParseResult(None, "record must be a JSON object")
    return _checked(value, max_fields)


def _checked(record: Dict[str, Any], max_fields: int) -> ParseResult:
    if len(record) > max_fields:
        return ParseResult(None, f"record exceeds field limit ({max_fields})")
    if any(not isinstance(key, str) for key in record):
        return ParseResult(None, "field names must be strings")
    return ParseResult(record)
