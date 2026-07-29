"""Conservative input format detection."""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import List, Optional, Tuple

SUPPORTED_FORMATS = ("csv", "tsv", "json", "jsonl", "whitespace", "keyvalue", "stream")


class AmbiguousFormatError(ValueError):
    pass


def detect_format(sample: str, filename: Optional[str] = None) -> Tuple[str, List[str]]:
    text = sample.lstrip("\ufeff \t\r\n")
    warnings: List[str] = []
    if not text:
        raise AmbiguousFormatError("empty input cannot be auto-detected; use --format")
    suffix = Path(filename).suffix.lower() if filename else ""
    if text.startswith("["):
        try:
            value = json.loads(text)
            if isinstance(value, list):
                return "json", warnings
        except json.JSONDecodeError:
            pass
    lines = [line for line in text.splitlines() if line.strip()]
    if lines:
        json_objects = 0
        for line in lines[:20]:
            try:
                if isinstance(json.loads(line), dict):
                    json_objects += 1
            except json.JSONDecodeError:
                break
        if json_objects == min(20, len(lines)):
            return "jsonl", warnings
    if lines and all(
        len(re.findall(r"(?:^|\s)[^=\s]+=[^\s]+", line)) >= 1 for line in lines[:10]
    ):
        return "keyvalue", warnings
    if suffix == ".tsv" or (lines and "\t" in lines[0]):
        return "tsv", warnings
    if suffix == ".csv":
        return "csv", warnings
    if lines and "," in lines[0]:
        rows = list(csv.reader(io.StringIO("\n".join(lines[:10]))))
        if len({len(row) for row in rows}) == 1:
            first = rows[0]
            headerish = any(not _number(cell) for cell in first)
            if headerish:
                return "csv", warnings
            raise AmbiguousFormatError(
                "comma-separated numeric input is ambiguous; use --format stream or csv"
            )
    if lines and all(len(line.split()) > 1 for line in lines[:10]):
        if all(all(_number(cell) for cell in line.split()) for line in lines[:10]):
            return "whitespace", warnings
    raise AmbiguousFormatError("input format is ambiguous; specify --format")


def _number(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False
