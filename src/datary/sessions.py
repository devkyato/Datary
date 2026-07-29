"""Session discovery, loading, and integrity verification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Union

from datary.config import SESSION_FORMAT_VERSION, default_workspace
from datary.models import Record
from datary.utils import json_lines, safe_name, sha256_file


@dataclass(frozen=True)
class Session:
    path: Path
    manifest: Dict[str, Any]

    @classmethod
    def open(cls, source: Union[str, Path], workspace: Union[str, Path, None] = None) -> "Session":
        candidate = Path(source)
        root = Path(workspace) if workspace else default_workspace()
        if not candidate.exists():
            candidate = root / safe_name(str(source))
        candidate = candidate.resolve()
        if candidate.is_symlink():
            raise ValueError("session directories may not be symbolic links")
        manifest_path = candidate / "manifest.json"
        if not candidate.is_dir() or not manifest_path.is_file() or manifest_path.is_symlink():
            raise ValueError(f"not a Datary session: {source}")
        try:
            value = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"broken session manifest: {error}") from error
        if not isinstance(value, dict):
            raise ValueError("session manifest must be an object")
        if value.get("session_format_version") != SESSION_FORMAT_VERSION:
            raise ValueError("unsupported session format version")
        for required in ("session_name", "record_count", "hashes"):
            if required not in value:
                raise ValueError(f"manifest is missing {required}")
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
        hashes = self.manifest.get("hashes", {})
        if not isinstance(hashes, dict):
            return ["manifest hashes must be an object"]
        for relative, expected in hashes.items():
            if not isinstance(relative, str) or Path(relative).name != relative:
                errors.append(f"unsafe hash path: {relative!r}")
                continue
            target = self.path / relative
            if not target.is_file() or target.is_symlink():
                errors.append(f"missing or unsafe file: {relative}")
            elif sha256_file(target) != expected:
                errors.append(f"hash mismatch: {relative}")
        return errors


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

