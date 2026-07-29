"""Small safety and serialization helpers."""

from __future__ import annotations

import hashlib
import html
import json
import math
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any, Callable, Dict, Iterable, Iterator, List, NoReturn, Optional


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


def atomic_text(path: Path, value: str, encoding: str = "utf-8") -> None:
    """Atomically replace a regular text file without following an output symlink."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("output path may not be a symbolic link")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as stream:
            stream.write(value)
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


def bounded_text_lines(stream: IO[str], maximum: int) -> Iterator[str]:
    """Read physical lines without first allocating an unbounded line."""

    if maximum <= 0:
        raise ValueError("line limit must be positive")
    while True:
        line = stream.readline(maximum + 1)
        if not line:
            return
        _validate_text_line(line, maximum)
        if line.endswith(("\n", "\r")):
            yield line
            continue
        continuation = stream.readline(1)
        if not continuation:
            yield line
            return
        combined = line + continuation
        _validate_text_line(combined, maximum)
        if continuation in {"\n", "\r"}:
            yield combined
            continue
        raise ValueError(f"input line exceeds byte limit ({maximum})")


def _validate_text_line(line: str, maximum: int) -> None:
    if len(line.encode("utf-8")) > maximum:
        raise ValueError(f"input line exceeds byte limit ({maximum})")


def safe_name(value: str) -> str:
    if not value or value in {".", ".."} or Path(value).name != value:
        raise ValueError("session name must be a single, non-empty path component")
    cleaned = re.sub(r"[^\w.-]", "-", value, flags=re.UNICODE).strip(".-")
    if not cleaned:
        raise ValueError("session name contains no safe characters")
    if len(cleaned) > 120:
        raise ValueError("session name exceeds 120 characters")
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved.update(f"COM{number}" for number in range(1, 10))
    reserved.update(f"LPT{number}" for number in range(1, 10))
    if cleaned.split(".", 1)[0].upper() in reserved:
        raise ValueError("session name is reserved by Windows filesystems")
    return cleaned


def safe_output(base: Path, requested: Path) -> Path:
    base_resolved = base.resolve()
    candidate = requested if requested.is_absolute() else base / requested
    resolved = candidate.resolve()
    if resolved != base_resolved and base_resolved not in resolved.parents:
        raise ValueError("output path escapes the allowed destination")
    return resolved


def safe_filename_component(value: str, fallback: str = "output") -> str:
    """Return a display-derived filename component with no path semantics."""

    cleaned = re.sub(r"[^\w.-]+", "-", value, flags=re.UNICODE).strip(".-")
    if not cleaned:
        cleaned = fallback
    return cleaned[:120]


def csv_safe_cell(value: Any) -> Any:
    """Render nested values and neutralize spreadsheet formula prefixes.

    The canonical value remains unchanged in ``records.jsonl``. CSV is a
    convenience export and receives a leading apostrophe for formula-like
    strings so opening it in a spreadsheet does not execute cell formulas.
    """

    if isinstance(value, (dict, list)):
        rendered = json.dumps(value, sort_keys=True, ensure_ascii=False)
    else:
        rendered = value
    if isinstance(rendered, str):
        stripped = rendered.lstrip()
        if stripped.startswith(("=", "+", "-", "@")):
            return "'" + rendered
    return rendered


def finite_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, int) and abs(value) > 2**53:
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    return None


def temporal_number(value: Any) -> Optional[float]:
    """Return numeric seconds for a finite number or timezone-aware ISO 8601 value."""

    number = finite_number(value)
    if number is not None:
        return number
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.endswith(("Z", "z")):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.timestamp()


def terminal_safe(value: object, maximum: int = 4096) -> str:
    """Render untrusted text without emitting terminal control sequences."""

    text = str(value)
    rendered: List[str] = []
    for character in text:
        code = ord(character)
        if code < 32 or 127 <= code <= 159:
            rendered.append(f"\\x{code:02x}")
        else:
            rendered.append(character)
    result = "".join(rendered)
    return result if len(result) <= maximum else result[: maximum - 1] + "…"


def markdown_safe(value: object) -> str:
    """Escape untrusted text for ordinary Markdown and Markdown tables."""

    escaped = html.escape(str(value), quote=True)
    for character in (
        "\\",
        "`",
        "*",
        "_",
        "{",
        "}",
        "[",
        "]",
        "(",
        ")",
        "#",
        "+",
        "-",
        ".",
        "!",
        "|",
        ">",
    ):
        escaped = escaped.replace(character, f"\\{character}")
    return escaped.replace("\r", " ").replace("\n", " ")


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
    if len(items) > 1000:
        raise ValueError("too many KEY=VALUE options (maximum 1000)")
    result: Dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"expected KEY=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        if not key:
            raise ValueError("key may not be empty")
        if len(key) > 120 or len(value) > 4096:
            raise ValueError("KEY=VALUE option exceeds the safety limit")
        result[key] = value
    return result


def sparkline(values: List[float], ascii_only: bool = False) -> str:
    if not values:
        return ""
    chars = ".:-=+*#@" if ascii_only else "▁▂▃▄▅▆▇█"
    low, high = min(values), max(values)
    if high == low:
        return chars[len(chars) // 2] * len(values)
    return "".join(
        chars[min(len(chars) - 1, int((v - low) / (high - low) * len(chars)))] for v in values
    )


def json_lines(path: Path, max_line_bytes: int = 16 * 1024 * 1024) -> Iterator[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if line.strip():
                if len(line.encode("utf-8")) > max_line_bytes:
                    raise ValueError(
                        f"records line {line_number} exceeds byte limit ({max_line_bytes})"
                    )
                try:
                    value = json.loads(
                        line,
                        parse_constant=_constant_rejector(line_number),
                    )
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"invalid records JSON at line {line_number}: {error.msg}"
                    ) from error
                if not isinstance(value, dict):
                    raise ValueError(f"records line {line_number} must contain a JSON object")
                yield value


def _constant_rejector(line_number: int) -> Callable[[str], NoReturn]:
    def reject(constant: str) -> NoReturn:
        _reject_constant(constant, line_number)

    return reject


def _reject_constant(constant: str, line_number: int) -> NoReturn:
    raise ValueError(f"non-finite JSON number {constant!r} in records line {line_number}")
