"""Explainable data-quality checks."""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter
from typing import Any, List, Optional, Sequence, Tuple

from datary.models import Finding, Record
from datary.utils import finite_number, temporal_number


def _finding(
    check_id: str,
    severity: str,
    field: Optional[str],
    affected: str,
    evidence: Any,
    threshold: Any,
    explanation: str,
    assumptions: Optional[List[str]] = None,
    suggestion: str = "Inspect the affected raw records and confirm domain expectations.",
) -> Finding:
    return Finding(
        check_id,
        severity,
        field,
        affected,
        evidence,
        threshold,
        explanation,
        assumptions or [],
        suggestion,
    )


def analyze_quality(
    records: Sequence[Record],
    time_field: Optional[str] = None,
    sequence_field: Optional[str] = None,
    monotonic_fields: Optional[Sequence[str]] = None,
    counter_fields: Optional[Sequence[str]] = None,
) -> List[Finding]:
    findings: List[Finding] = []
    monotonic = set(monotonic_fields or ())
    counters = set(counter_fields or ())
    if not records:
        return [
            _finding(
                "empty-data",
                "warning",
                None,
                "all",
                0,
                "> 0 records",
                "No valid records were parsed.",
            )
        ]
    fields = sorted({key for record in records for key in record})
    serialized = [json.dumps(record, sort_keys=True, ensure_ascii=False) for record in records]
    duplicates = sum(count - 1 for count in Counter(serialized).values() if count > 1)
    if duplicates:
        findings.append(
            _finding(
                "duplicate-rows",
                "warning",
                None,
                "multiple",
                duplicates,
                0,
                "Identical records recur.",
            )
        )
    schemas = {tuple(sorted(record)) for record in records}
    if len(schemas) > 1:
        findings.append(
            _finding(
                "record-shape-change",
                "warning",
                None,
                "multiple",
                [list(schema) for schema in sorted(schemas)],
                "one stable field set",
                "Record field names change across the dataset.",
            )
        )
    lengths = {len(schema) for schema in schemas}
    if len(lengths) > 1:
        findings.append(
            _finding(
                "record-length-change",
                "warning",
                None,
                "multiple",
                sorted(lengths),
                1,
                "Record field counts vary.",
            )
        )
    for field in fields:
        values = [record.get(field) for record in records]
        missing = [index for index, value in enumerate(values) if value is None or value == ""]
        if missing:
            findings.append(
                _finding(
                    "missing-values",
                    "warning",
                    field,
                    _range(missing),
                    len(missing),
                    0,
                    "Values are absent.",
                )
            )
        types = sorted({type(value).__name__ for value in values if value is not None})
        if len(types) > 1 and not set(types) <= {"int", "float"}:
            findings.append(
                _finding(
                    "type-change", "warning", field, "multiple", types, 1, "The field changes type."
                )
            )
        nonfinite = [
            index
            for index, value in enumerate(values)
            if isinstance(value, float) and (math.isnan(value) or math.isinf(value))
        ]
        if nonfinite:
            findings.append(
                _finding(
                    "non-finite",
                    "error",
                    field,
                    _range(nonfinite),
                    len(nonfinite),
                    0,
                    "NaN or infinity is not a finite measurement.",
                )
            )
        large_integers = [
            index
            for index, value in enumerate(values)
            if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 2**53
        ]
        if large_integers:
            findings.append(
                _finding(
                    "invalid-values",
                    "warning",
                    field,
                    _range(large_integers),
                    len(large_integers),
                    "integer magnitude ≤ 2^53 for exact binary64 analysis",
                    "Large integers were preserved but excluded from numeric analysis.",
                )
            )
        numbers = [(index, finite_number(value)) for index, value in enumerate(values)]
        clean = [(index, value) for index, value in numbers if value is not None]
        if len(clean) >= 2 and field not in {time_field, sequence_field}:
            numeric = [float(value) for _, value in clean]
            decreases = [
                clean[index][0]
                for index in range(1, len(clean))
                if numeric[index] < numeric[index - 1]
            ]
            if field in monotonic and decreases:
                findings.append(
                    _finding(
                        "monotonicity-violation",
                        "warning",
                        field,
                        _range(decreases),
                        len(decreases),
                        "no decreases",
                        "The field decreases despite an explicit monotonicity expectation.",
                        ["Missing values are ignored between consecutive valid values."],
                        "Confirm ordering and whether resets or wraparound are expected.",
                    )
                )
            if field in counters and decreases:
                findings.append(
                    _finding(
                        "counter-reset",
                        "warning",
                        field,
                        _range(decreases),
                        len(decreases),
                        "no decreases",
                        "The counter decreases, indicating a reset, rollover, or reordered record.",
                        ["The selected field is expected to be a non-decreasing counter."],
                        "Check device restarts, counter width, wraparound, and record ordering.",
                    )
                )
            if max(numeric) == min(numeric):
                findings.append(
                    _finding(
                        "constant-signal",
                        "info",
                        field,
                        f"{clean[0][0]}-{clean[-1][0]}",
                        numeric[0],
                        "no variation",
                        "The signal is constant.",
                    )
                )
            frozen = _longest_run(clean)
            if frozen[1] >= 5 and frozen[1] < len(numeric):
                findings.append(
                    _finding(
                        "frozen-values",
                        "warning",
                        field,
                        f"{frozen[0]}-{frozen[2]}",
                        frozen[1],
                        5,
                        "The same value repeats for an extended run.",
                        ["Missing values break a frozen run."],
                    )
                )
            if len(numeric) >= 5:
                median = statistics.median(numeric)
                deviations = [abs(value - median) for value in numeric]
                mad = statistics.median(deviations)
                outliers = [
                    clean[i][0]
                    for i, value in enumerate(numeric)
                    if (abs(value - median) > 6 * mad if mad > 0 else value != median)
                ]
                if outliers:
                    threshold = "6 × MAD" if mad > 0 else "different from zero-MAD median"
                    findings.append(
                        _finding(
                            "outliers",
                            "warning",
                            field,
                            _range(outliers),
                            len(outliers),
                            threshold,
                            "Values are far from the median.",
                            ["Robust median absolute deviation rule."],
                        )
                    )
                diffs = [abs(b - a) for a, b in zip(numeric, numeric[1:])]
                base = statistics.median(diffs)
                spikes = [
                    clean[i + 1][0]
                    for i, value in enumerate(diffs)
                    if (value > base * 10 if base > 0 else value > 0)
                ]
                if spikes:
                    threshold = (
                        "10 × median absolute step"
                        if base > 0
                        else "non-zero step after zero baseline"
                    )
                    findings.append(
                        _finding(
                            "sudden-spikes",
                            "warning",
                            field,
                            _range(spikes),
                            len(spikes),
                            threshold,
                            "Abrupt changes exceed the configured robust threshold.",
                        )
                    )
                mean = statistics.fmean(numeric)
                if mean and statistics.pstdev(numeric) / abs(mean) > 0.5:
                    findings.append(
                        _finding(
                            "high-noise",
                            "info",
                            field,
                            "all",
                            statistics.pstdev(numeric),
                            "coefficient of variation > 0.5",
                            "Variation is high relative to the mean.",
                            ["Only meaningful for ratio-scale signals."],
                        )
                    )
    if time_field and time_field in fields:
        times = [
            (index, temporal_number(record.get(time_field))) for index, record in enumerate(records)
        ]
        clean_times = [(index, float(value)) for index, value in times if value is not None]
        intervals = [
            (clean_times[i][0], clean_times[i][1] - clean_times[i - 1][1])
            for i in range(1, len(clean_times))
        ]
        seen_times: set[float] = set()
        duplicate_times: List[int] = []
        for index, value in clean_times:
            if value in seen_times:
                duplicate_times.append(index)
            else:
                seen_times.add(value)
        _timing_findings(findings, time_field, intervals, duplicate_times)
    if sequence_field and sequence_field in fields:
        sequence = [finite_number(record.get(sequence_field)) for record in records]
        invalid_sequence = [
            index
            for index, value in enumerate(sequence)
            if value is not None and not float(value).is_integer()
        ]
        if invalid_sequence:
            findings.append(
                _finding(
                    "invalid-values",
                    "warning",
                    sequence_field,
                    _range(invalid_sequence),
                    len(invalid_sequence),
                    "integer sequence identifiers",
                    "Sequence identifiers contain non-integer numeric values.",
                )
            )
        clean_seq = [
            int(value) for value in sequence if value is not None and float(value).is_integer()
        ]
        if clean_seq:
            expected = max(clean_seq) - min(clean_seq) + 1
            lost = expected - len(set(clean_seq))
            if lost > 0:
                findings.append(
                    _finding(
                        "packet-loss",
                        "warning",
                        sequence_field,
                        "range",
                        lost,
                        0,
                        "Sequence identifiers contain gaps.",
                        ["Identifiers are expected to increase by one."],
                    )
                )
    return sorted(findings, key=lambda item: (item.check_id, item.field or "", item.affected))


def _timing_findings(
    findings: List[Finding],
    field: str,
    intervals: List[Tuple[int, float]],
    duplicate: Optional[List[int]] = None,
) -> None:
    duplicate = duplicate or [index for index, value in intervals if value == 0]
    backward = [index for index, value in intervals if value < 0]
    positive = [value for _, value in intervals if value > 0]
    if duplicate:
        findings.append(
            _finding(
                "duplicate-timestamps",
                "warning",
                field,
                _range(duplicate),
                len(duplicate),
                0,
                "Adjacent timestamps are equal.",
            )
        )
    if backward:
        findings.append(
            _finding(
                "timestamps-backwards",
                "error",
                field,
                _range(backward),
                len(backward),
                0,
                "Time moves backwards.",
            )
        )
    if len(positive) > 2:
        median = statistics.median(positive)
        irregular = [
            index for index, value in intervals if value > 0 and abs(value - median) > median * 0.2
        ]
        gaps = [index for index, value in intervals if value > median * 2]
        if irregular:
            findings.append(
                _finding(
                    "irregular-timing",
                    "warning",
                    field,
                    _range(irregular),
                    len(irregular),
                    "±20% of median interval",
                    "Sampling intervals vary.",
                )
            )
        if gaps:
            findings.append(
                _finding(
                    "large-timing-gaps",
                    "warning",
                    field,
                    _range(gaps),
                    len(gaps),
                    "2 × median interval",
                    "Large gaps occur in sampling.",
                )
            )


def _longest_run(values: List[Tuple[int, float]]) -> Tuple[int, int, int]:
    best_start = current_start = 0
    best_length = current_length = 1
    for index in range(1, len(values)):
        if (
            values[index][1] == values[index - 1][1]
            and values[index][0] == values[index - 1][0] + 1
        ):
            current_length += 1
        else:
            current_start, current_length = index, 1
        if current_length > best_length:
            best_start, best_length = current_start, current_length
    return values[best_start][0], best_length, values[best_start + best_length - 1][0]


def _range(indices: List[int]) -> str:
    return str(indices[0]) if len(indices) == 1 else f"{indices[0]}-{indices[-1]}"
