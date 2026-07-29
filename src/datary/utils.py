"""Small safety and serialization helpers."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_name(value: str) -> str:
    if not value or value in {".", ".."} or Path(value).name != value:
        raise ValueError("session name must be a single, non-empty path component")
    cleaned = re.sub(r"[^\w.-]", "-", value, flags=re.UNICODE).strip(".-")
    if not cleaned:
        raise ValueError("session name contains no safe characters")
    return cleaned


def safe_output(base: Path, requested: Path) -> Path:
    base_resolved = base.resolve()
    candidate = requested if requested.is_absolute() else base / requested
    resolved = candidate.resolve()
    if resolved != base_resolved and base_resolved not in resolved.parents:
        raise ValueError("output path escapes the allowed destination")
    return resolved


def finite_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    return None


def infer_type(values: Iterable[Any]) -> str:
    names = {type(value).__name__ for value in values if value is not None}
    if not names:
        return "null"
    if names <= {"int"}:
        return "integer"
    if names <= {"int", "float"}:
        return "number"
    if len(names) == 1:
        return next(iter(names))
    return "mixed"


def parse_key_values(items: List[str]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"expected KEY=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        if not key:
            raise ValueError("key may not be empty")
        result[key] = value
    return result


def sparkline(values: List[float], ascii_only: bool = False) -> str:
    if not values:
        return ""
    chars = ".:-=+*#@" if ascii_only else "▁▂▃▄▅▆▇█"
    low, high = min(values), max(values)
    if high == low:
        return chars[len(chars) // 2] * len(values)
    return "".join(chars[min(len(chars) - 1, int((v - low) / (high - low) * len(chars)))] for v in values)


def json_lines(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    yield value
