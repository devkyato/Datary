"""Session discovery, loading, and integrity verification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Union

from datary.config import SUPPORTED_SESSION_FORMAT_VERSIONS, default_workspace
from datary.formats import SUPPORTED_FORMATS
from datary.models import Record
from datary.utils import json_lines, safe_name, sha256_file


@dataclass(frozen=True)
class Session:
    path: Path
    manifest: Dict[str, Any]

    @classmethod
    def open(cls, source: Union[str, Path], workspace: Union[str, Path, None] = None) -> "Session":
        candidate = Path(source)
        root = (Path(workspace) if workspace else default_workspace()).resolve()
        if candidate.is_symlink():
            raise ValueError("session directories may not be symbolic links")
        if not candidate.exists():
            candidate = root / safe_name(str(source))
            try:
                candidate.relative_to(root)
            except ValueError as error:
                raise ValueError("named session escapes the configured workspace") from error
        if _contains_symlink(candidate):
            raise ValueError("session paths may not contain symbolic links")
        candidate = candidate.resolve()
        manifest_path = candidate / "manifest.json"
        if not candidate.is_dir() or not manifest_path.is_file() or manifest_path.is_symlink():
            raise ValueError(f"not a Datary session: {source}")
        if manifest_path.stat().st_size > 1_048_576:
            raise ValueError("session manifest exceeds the 1 MiB safety limit")
        try:
            value = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"broken session manifest: {error}") from error
        if not isinstance(value, dict):
            raise ValueError("session manifest must be an object")
        if value.get("session_format_version") not in SUPPORTED_SESSION_FORMAT_VERSIONS:
            raise ValueError("unsupported session format version")
        for required in ("session_name", "record_count", "hashes"):
            if required not in value:
                raise ValueError(f"manifest is missing {required}")
        if value.get("session_format_version") == "2":
            for required in ("valid_record_count", "invalid_record_count"):
                if required not in value:
                    raise ValueError(f"manifest is missing {required}")
        if safe_name(str(value["session_name"])) != value["session_name"]:
            raise ValueError("manifest has an unsafe session name")
        count_names = ["record_count"]
        if "valid_record_count" in value:
            count_names.append("valid_record_count")
        if "invalid_record_count" in value:
            count_names.append("invalid_record_count")
        for count_name in count_names:
            count = value[count_name]
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ValueError(f"manifest {count_name} must be a non-negative integer")
        if (
            "valid_record_count" in value
            and "invalid_record_count" in value
            and value["record_count"] != value["valid_record_count"] + value["invalid_record_count"]
        ):
            raise ValueError("manifest record counts are inconsistent")
        hashes = value["hashes"]
        if not isinstance(hashes, dict) or len(hashes) > 100:
            raise ValueError("manifest hashes must be a bounded object")
        if value.get("session_format_version") == "2":
            _validate_v2_manifest(value)
        return cls(candidate, value)

    @property
    def name(self) -> str:
        return str(self.manifest["session_name"])

    def records(self) -> Iterator[Record]:
        records_path = self.path / "records.jsonl"
        if records_path.is_symlink():
            raise ValueError("session records may not be symbolic links")
        yield from json_lines(records_path)

    def verify(self) -> List[str]:
        errors: List[str] = []
        manifest_digest_path = self.path / "manifest.sha256"
        if self.manifest.get("session_format_version") == "2":
            if not manifest_digest_path.is_file() or manifest_digest_path.is_symlink():
                errors.append("missing or unsafe file: manifest.sha256")
            else:
                expected_manifest = manifest_digest_path.read_text(encoding="ascii").strip()
                if (
                    len(expected_manifest) != 64
                    or any(character not in "0123456789abcdef" for character in expected_manifest)
                    or expected_manifest != sha256_file(self.path / "manifest.json")
                ):
                    errors.append("hash mismatch: manifest.json")
        hashes = self.manifest.get("hashes", {})
        if not isinstance(hashes, dict):
            return ["manifest hashes must be an object"]
        for relative, expected in hashes.items():
            if (
                not isinstance(relative, str)
                or Path(relative).name != relative
                or not isinstance(expected, str)
                or len(expected) != 64
                or any(character not in "0123456789abcdef" for character in expected)
            ):
                errors.append(f"unsafe hash path: {relative!r}")
                continue
            target = self.path / relative
            if not target.is_file() or target.is_symlink():
                errors.append(f"missing or unsafe file: {relative}")
            elif sha256_file(target) != expected:
                errors.append(f"hash mismatch: {relative}")
        if self.manifest.get("session_format_version") == "2":
            required = {
                "raw.log",
                "records.jsonl",
                "invalid.jsonl",
                "data.csv",
                "metrics.json",
                "quality.json",
                "notes.md",
            }
            for missing in sorted(required - set(hashes)):
                errors.append(f"unhashed required file: {missing}")
            if "records.jsonl" not in {
                error.removeprefix("hash mismatch: ")
                for error in errors
                if error.startswith("hash mismatch: ")
            }:
                try:
                    valid_count = sum(1 for _ in self.records())
                    if valid_count != self.manifest["valid_record_count"]:
                        errors.append(
                            "record count mismatch: records.jsonl "
                            f"has {valid_count}, manifest has "
                            f"{self.manifest['valid_record_count']}"
                        )
                except (OSError, ValueError, json.JSONDecodeError) as error:
                    errors.append(f"invalid records.jsonl: {error}")
            try:
                invalid_count = _count_invalid_records(self.path / "invalid.jsonl")
                if invalid_count != self.manifest["invalid_record_count"]:
                    errors.append(
                        "record count mismatch: invalid.jsonl "
                        f"has {invalid_count}, manifest has "
                        f"{self.manifest['invalid_record_count']}"
                    )
            except (OSError, ValueError, json.JSONDecodeError) as error:
                errors.append(f"invalid invalid.jsonl: {error}")
        return errors


def _contains_symlink(path: Path) -> bool:
    """Check each existing path component before resolution changes its identity."""

    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            if current.is_symlink():
                return True
        except OSError:
            return True
    return False


def _validate_v2_manifest(value: Dict[str, Any]) -> None:
    for name in (
        "datary_version",
        "parser_policy",
        "working_directory",
        "integrity_scope",
        "command_context",
    ):
        if not isinstance(value.get(name), str):
            raise ValueError(f"manifest {name} must be a string")
    if value["parser_policy"] != "conservative-scalars-v1":
        raise ValueError("manifest uses an unsupported parser policy")
    if value.get("original_command") is not None and not isinstance(
        value.get("original_command"), str
    ):
        raise ValueError("manifest original command must be a string or null")
    if not isinstance(value.get("interrupted"), bool):
        raise ValueError("manifest interrupted flag must be boolean")
    sampling = value.get("sampling")
    if not isinstance(sampling, dict) or len(sampling) > 100:
        raise ValueError("manifest sampling must be a bounded object")
    if value.get("input_format") not in SUPPORTED_FORMATS:
        raise ValueError("manifest has an unsupported input format")
    for name in ("fields", "units", "parameters", "commands", "field_roles"):
        mapping = value.get(name)
        if not isinstance(mapping, dict) or len(mapping) > 1000:
            raise ValueError(f"manifest {name} must be a bounded object")
        if any(
            not isinstance(key, str) or not isinstance(item, str) for key, item in mapping.items()
        ):
            raise ValueError(f"manifest {name} entries must be strings")
    parser_warnings = value.get("parser_warnings", [])
    if not isinstance(parser_warnings, list) or any(
        not isinstance(item, str) for item in parser_warnings
    ):
        raise ValueError("manifest parser warnings must be strings")
    if len(parser_warnings) > 100:
        raise ValueError("manifest contains too many parser warnings")
    if value.get("time_field") is not None and not isinstance(value.get("time_field"), str):
        raise ValueError("manifest time field must be a string or null")
    for timestamp_name in ("started_at", "ended_at"):
        timestamp = value.get(timestamp_name)
        if not isinstance(timestamp, str):
            raise ValueError(f"manifest {timestamp_name} must be an ISO 8601 string")
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"manifest {timestamp_name} is not valid ISO 8601") from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(f"manifest {timestamp_name} must include a timezone")


def _count_invalid_records(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            if len(line.encode("utf-8")) > 1_048_576:
                raise ValueError(f"line {line_number} exceeds the safety limit")
            value = json.loads(line)
            if (
                not isinstance(value, dict)
                or not isinstance(value.get("record"), int)
                or not isinstance(value.get("reason"), str)
            ):
                raise ValueError(f"line {line_number} has an invalid error record")
            count += 1
    return count


def list_sessions(workspace: Union[str, Path, None] = None) -> List[Session]:
    root = Path(workspace) if workspace else default_workspace()
    if not root.exists():
        return []
    sessions: List[Session] = []
    for child in sorted(root.iterdir(), key=lambda path: path.name.casefold()):
        if child.is_dir() and not child.is_symlink() and (child / "manifest.json").is_file():
            try:
                sessions.append(Session.open(child))
            except ValueError:
                pass
    return sessions
