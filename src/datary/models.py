"""Shared typed models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

JsonScalar = Union[None, bool, int, float, str]
JsonValue = Union[JsonScalar, List["JsonValue"], Dict[str, "JsonValue"]]
Record = Dict[str, JsonValue]


@dataclass
class Finding:
    check_id: str
    severity: str
    field: Optional[str]
    affected: str
    evidence: JsonValue
    threshold: JsonValue
    explanation: str
    assumptions: List[str] = dataclass_field(default_factory=list)
    suggested_investigation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ParseResult:
    record: Optional[Record]
    error: Optional[str] = None


@dataclass
class Inspection:
    source: str
    format: str
    record_count: int
    invalid_count: int
    fields: Dict[str, str]
    metrics: Dict[str, Any]
    timing: Dict[str, Any]
    quality: List[Dict[str, Any]]
    units: Dict[str, str] = dataclass_field(default_factory=dict)
    engineering: Dict[str, Any] = dataclass_field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Comparison:
    sources: List[str]
    fields: Dict[str, Dict[str, Any]]
    warnings: List[str]
    goal: Optional[str] = None
    timing: Dict[str, Any] = dataclass_field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RecordOptions:
    name: str
    workspace: Path
    input_format: Optional[str] = None
    time_field: Optional[str] = None
    command: Optional[str] = None
    parameters: Dict[str, str] = dataclass_field(default_factory=dict)
    units: Dict[str, str] = dataclass_field(default_factory=dict)
    overwrite: bool = False
    include_path: bool = False
    max_line_bytes: int = 1_048_576
    max_fields: int = 1_000
    target_field: Optional[str] = None
    response_field: Optional[str] = None
    sequence_field: Optional[str] = None
    latency_field: Optional[str] = None
    bytes_field: Optional[str] = None
