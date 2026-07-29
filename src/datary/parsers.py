"""Streaming parsers. Input is always treated as inert text."""

from __future__ import annotations

import csv
import json
import re
import shlex
import threading
from typing import Any, Dict, Iterable, Iterator, Optional

from datary.models import ParseResult, Record

_CANONICAL_INTEGER = re.compile(r"-?(?:0|[1-9]\d*)\Z")
_CANONICAL_FLOAT = re.compile(
    r"-?(?:(?:0|[1-9]\d*)\.\d+|(?:0|[1-9]\d*)(?:[eE][+-]?\d+)|"
    r"(?:0|[1-9]\d*)\.\d+(?:[eE][+-]?\d+))\Z"
)
_MAX_JSON_BUFFER_BYTES = 16 * 1024 * 1024
_MAX_CSV_FIELD_CHARACTERS = 16 * 1024 * 1024
_CSV_LIMIT_LOCK = threading.Lock()


def scalar(value: str) -> Any:
    """Apply Datary's conservative, documented scalar-coercion policy.

    Empty cells become missing values. Canonical JSON booleans and canonical
    numbers are converted. Identifier-like values such as ``00123`` and
    domain tokens such as ``NA`` remain strings.
    """

    stripped = value.strip()
    if stripped == "":
        return None
    if stripped == "true":
        return True
    if stripped == "false":
        return False
    if _CANONICAL_INTEGER.fullmatch(stripped):
        return int(stripped)
    if _CANONICAL_FLOAT.fullmatch(stripped):
        number = float(stripped)
        if not _is_finite(number):
            return stripped
        return number
    return stripped


def parse_lines(
    lines: Iterable[str],
    input_format: str,
    max_fields: int = 1000,
) -> Iterator[ParseResult]:
    """Parse records without executing input or silently accepting non-finite JSON."""

    if max_fields <= 0:
        raise ValueError("max_fields must be positive")
    clean_lines = _without_bom(lines)
    if input_format in {"csv", "tsv"}:
        yield from _delimited(clean_lines, "\t" if input_format == "tsv" else ",", max_fields)
        return
    if input_format == "json":
        yield from _json_array(clean_lines, max_fields)
        return
    for line_number, line in enumerate(clean_lines, 1):
        text = line.rstrip("\r\n")
        if not text.strip():
            yield ParseResult(None, f"line {line_number}: empty line")
            continue
        try:
            if input_format == "jsonl":
                result = _json_record(_json_loads(text), max_fields)
            elif input_format == "keyvalue":
                pairs = shlex.split(text)
                record: Record = {}
                for pair in pairs:
                    if "=" not in pair:
                        raise ValueError(f"token lacks '=': {pair}")
                    key, value = pair.split("=", 1)
                    if not key:
                        raise ValueError("field name may not be empty")
                    if key in record:
                        raise ValueError(f"duplicate field name: {key}")
                    record[key] = scalar(value)
                result = _checked(record, max_fields)
            elif input_format == "whitespace":
                result = _checked(
                    {
                        f"field_{index + 1}": scalar(value)
                        for index, value in enumerate(text.split())
                    },
                    max_fields,
                )
            elif input_format == "stream":
                result = _checked(
                    {
                        f"field_{index + 1}": scalar(value)
                        for index, value in enumerate(next(csv.reader([text], strict=True)))
                    },
                    max_fields,
                )
            else:
                result = ParseResult(None, f"unsupported format: {input_format}")
        except (ValueError, json.JSONDecodeError, csv.Error, RecursionError) as error:
            result = ParseResult(None, f"line {line_number}: {error}")
        yield result


def _delimited(lines: Iterable[str], delimiter: str, max_fields: int) -> Iterator[ParseResult]:
    """Parse RFC-style CSV records, including quoted embedded newlines."""

    reader = csv.reader(lines, delimiter=delimiter, strict=True)
    try:
        header = _next_csv_row(reader)
    except StopIteration:
        return
    except csv.Error as error:
        yield ParseResult(None, f"invalid header: {error}")
        return
    if not header or len(set(header)) != len(header) or any(not name.strip() for name in header):
        yield ParseResult(None, "header fields must be non-empty and unique")
        return
    if len(header) > max_fields:
        yield ParseResult(None, f"header exceeds field limit ({max_fields})")
        return
    while True:
        try:
            row = _next_csv_row(reader)
        except StopIteration:
            return
        except csv.Error as error:
            yield ParseResult(None, f"line {reader.line_num}: {error}")
            return
        if len(row) != len(header):
            yield ParseResult(
                None,
                f"line {reader.line_num}: expected {len(header)} fields, got {len(row)}",
            )
        else:
            yield _checked(dict(zip(header, map(scalar, row))), max_fields)


def _next_csv_row(reader: Any) -> list[str]:
    with _CSV_LIMIT_LOCK:
        previous_limit = csv.field_size_limit()
        csv.field_size_limit(_MAX_CSV_FIELD_CHARACTERS)
        try:
            row = next(reader)
            return list(row)
        finally:
            csv.field_size_limit(previous_limit)


def _json_array(lines: Iterable[str], max_fields: int) -> Iterator[ParseResult]:
    """Incrementally decode a top-level JSON array with a bounded pending buffer."""

    decoder = json.JSONDecoder(
        parse_constant=_reject_json_constant,
        object_pairs_hook=_object_without_duplicates,
    )
    iterator = iter(lines)
    buffer = ""
    position = 0
    finished = False

    def fill() -> bool:
        nonlocal buffer, position, finished
        if finished:
            return False
        try:
            chunk = next(iterator)
        except StopIteration:
            finished = True
            return False
        if position:
            buffer = buffer[position:]
            position = 0
        buffer += chunk
        if len(buffer.encode("utf-8")) > _MAX_JSON_BUFFER_BYTES:
            raise ValueError(
                f"JSON record or pending document exceeds {_MAX_JSON_BUFFER_BYTES} bytes"
            )
        return True

    try:
        while not buffer and fill():
            pass
        position = _skip_space(buffer, position)
        while position >= len(buffer) and fill():
            position = _skip_space(buffer, position)
        if position >= len(buffer) or buffer[position] != "[":
            yield ParseResult(None, "JSON input must be an array")
            return
        position += 1
        item_number = 0
        expecting_item = True
        while True:
            position = _skip_space(buffer, position)
            while position >= len(buffer) and fill():
                position = _skip_space(buffer, position)
            if position >= len(buffer):
                yield ParseResult(None, "invalid JSON: unterminated array")
                return
            if buffer[position] == "]":
                if expecting_item and item_number:
                    yield ParseResult(None, "invalid JSON: trailing comma")
                    return
                position += 1
                break
            if not expecting_item:
                if buffer[position] != ",":
                    yield ParseResult(None, "invalid JSON: expected ',' between records")
                    return
                position += 1
                expecting_item = True
                continue
            while True:
                try:
                    value, end = decoder.raw_decode(buffer, position)
                    break
                except json.JSONDecodeError as error:
                    if fill():
                        continue
                    yield ParseResult(None, f"invalid JSON: {error.msg}")
                    return
            position = end
            item_number += 1
            yield _json_record(value, max_fields)
            expecting_item = False
        position = _skip_space(buffer, position)
        while fill():
            position = _skip_space(buffer, position)
        if buffer[position:].strip():
            yield ParseResult(None, "invalid JSON: trailing content after array")
    except (ValueError, RecursionError) as error:
        yield ParseResult(None, f"invalid JSON: {error}")


def _json_loads(text: str) -> Any:
    return json.loads(
        text,
        parse_constant=_reject_json_constant,
        object_pairs_hook=_object_without_duplicates,
    )


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _json_record(value: Any, max_fields: int) -> ParseResult:
    if not isinstance(value, dict):
        return ParseResult(None, "record must be a JSON object")
    return _checked(value, max_fields)


def _checked(record: Dict[str, Any], max_fields: int) -> ParseResult:
    if len(record) > max_fields:
        return ParseResult(None, f"record exceeds field limit ({max_fields})")
    if any(not isinstance(key, str) for key in record):
        return ParseResult(None, "field names must be strings")
    encoded_names = [len(key.encode("utf-8")) for key in record]
    if any(length > 1024 for length in encoded_names):
        return ParseResult(None, "field name exceeds 1024-byte limit")
    if sum(encoded_names) > 65_536:
        return ParseResult(None, "record field names exceed 65536-byte total limit")
    problem = _invalid_json_value(record)
    if problem:
        return ParseResult(None, problem)
    return ParseResult(record)


def _invalid_json_value(value: Any, path: str = "$") -> Optional[str]:
    if value is None or isinstance(value, (str, bool, int)):
        return None
    if isinstance(value, float):
        return None if _is_finite(value) else f"non-finite number at {path}"
    if isinstance(value, list):
        for index, item in enumerate(value):
            problem = _invalid_json_value(item, f"{path}[{index}]")
            if problem:
                return problem
        return None
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                return f"non-string object key at {path}"
            problem = _invalid_json_value(item, f"{path}.{key}")
            if problem:
                return problem
        return None
    return f"unsupported value type at {path}: {type(value).__name__}"


def _without_bom(lines: Iterable[str]) -> Iterator[str]:
    first = True
    for line in lines:
        if first:
            line = line.lstrip("\ufeff")
            first = False
        yield line


def _skip_space(value: str, position: int) -> int:
    while position < len(value) and value[position] in " \t\r\n":
        position += 1
    return position


def _is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))
