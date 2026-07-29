"""Deterministic, honest experiment comparison."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from datary.inspection import inspect_source
from datary.models import Comparison, Inspection


def compare_sessions(
    sources: Sequence[Union[str, Path]],
    fields: Optional[Sequence[str]] = None,
    goal: Optional[str] = None,
) -> Comparison:
    if len(sources) < 2:
        raise ValueError("comparison requires at least two sources")
    inspections = [inspect_source(source) for source in sources]
    labels = _unique_labels([str(source) for source in sources])
    common = set(inspections[0].metrics)
    for inspection in inspections[1:]:
        common &= set(inspection.metrics)
    selected = sorted(common & set(fields) if fields else common)
    warnings: List[str] = []
    requested = set(fields or ())
    for missing in sorted(requested - common):
        warnings.append(f"field {missing!r} is not numeric and shared by all sources")
    direction: Optional[str] = None
    goal_field: Optional[str] = None
    if goal:
        try:
            direction, goal_field = goal.split(":", 1)
        except ValueError as error:
            raise ValueError("goal must be lower:FIELD or higher:FIELD") from error
        if direction not in {"lower", "higher"}:
            raise ValueError("goal direction must be lower or higher")
    timing = _timing_context(inspections, labels, warnings)
    timing_comparable = bool(timing.get("sampling_rates_comparable", True))
    result: Dict[str, Dict[str, Any]] = {}
    for field in selected:
        means = {
            labels[index]: inspections[index].metrics[field].get("mean")
            for index in range(len(sources))
        }
        units = {
            labels[index]: inspections[index].units.get(field) for index in range(len(sources))
        }
        unit_values = set(units.values())
        units_comparable = len(unit_values) <= 1
        comparable = units_comparable and timing_comparable
        if not units_comparable:
            warnings.append(
                f"field {field!r} has incompatible declared units or missing unit declarations: "
                + ", ".join(f"{label}={unit or '<unspecified>'}" for label, unit in units.items())
            )
        statistics_by_source = {
            labels[index]: {
                key: inspections[index].metrics[field].get(key)
                for key in (
                    "valid_count",
                    "minimum",
                    "maximum",
                    "mean",
                    "median",
                    "standard_deviation",
                )
            }
            for index in range(len(sources))
        }
        detail: Dict[str, Any] = {
            "means": means,
            "statistics_by_source": statistics_by_source,
            "units": units,
            "comparable": comparable,
        }
        valid_counts = {
            label: statistics["valid_count"] for label, statistics in statistics_by_source.items()
        }
        if len(set(valid_counts.values())) > 1:
            warnings.append(
                f"field {field!r} has different valid sample counts: "
                + ", ".join(f"{label}={count}" for label, count in valid_counts.items())
            )
        baseline = next(iter(means.values()))
        if field == goal_field and comparable and baseline not in (None, 0):
            improvements: Dict[str, Optional[float]] = {}
            for name, value in means.items():
                if value is None:
                    improvements[name] = None
                elif direction == "lower":
                    improvements[name] = (baseline - value) / abs(baseline) * 100
                else:
                    improvements[name] = (value - baseline) / abs(baseline) * 100
            detail["improvement_percent_vs_first"] = improvements
        elif field == goal_field and baseline in (None, 0):
            warnings.append(
                f"goal field {field!r} has a missing or zero baseline mean; "
                "percentage improvement is undefined"
            )
        result[field] = detail
    if goal_field and goal_field not in result:
        warnings.append(f"goal field {goal_field!r} is not comparable")
    if not goal:
        warnings.append("no comparison goal supplied; no experiment is labelled better")
    return Comparison(labels, result, sorted(set(warnings)), goal, timing)


def _unique_labels(sources: Sequence[str]) -> List[str]:
    counts: Dict[str, int] = {}
    labels: List[str] = []
    for source in sources:
        counts[source] = counts.get(source, 0) + 1
        labels.append(source if counts[source] == 1 else f"{source}#{counts[source]}")
    return labels


def _timing_context(
    inspections: Sequence[Inspection],
    labels: Sequence[str],
    warnings: List[str],
) -> Dict[str, Any]:
    timed = [
        (labels[index], inspection.timing)
        for index, inspection in enumerate(inspections)
        if inspection.timing
    ]
    if len(timed) != len(inspections):
        warnings.append("one or more sources have no comparable numeric time field")
        return {}
    starts = [float(timing["start"]) for _, timing in timed if "start" in timing]
    ends = [float(timing["end"]) for _, timing in timed if "end" in timing]
    rates = {label: timing.get("effective_sample_rate") for label, timing in timed}
    positive_rates = [float(rate) for rate in rates.values() if rate]
    rates_comparable = not positive_rates or max(positive_rates) / min(positive_rates) <= 1.01
    if not rates_comparable:
        warnings.append(
            "sampling rates differ; descriptive statistics are shown without resampling "
            "and goal improvement is not calculated"
        )
    result: Dict[str, Any] = {
        "sample_rates": rates,
        "sampling_rates_comparable": rates_comparable,
    }
    if len(starts) == len(timed) and len(ends) == len(timed):
        shared_start = max(starts)
        shared_end = min(ends)
        result["ranges"] = {label: [timing["start"], timing["end"]] for label, timing in timed}
        result["shared_range"] = [shared_start, shared_end] if shared_start <= shared_end else None
        durations = {label: max(0.0, float(timing.get("duration", 0.0))) for label, timing in timed}
        result["relative_ranges"] = {
            label: [0.0, duration] for label, duration in durations.items()
        }
        result["shared_relative_range"] = [0.0, min(durations.values())]
        if shared_start > shared_end:
            warnings.append("sources have no shared time range")
        else:
            warnings.append(
                "time ranges are reported, but values are not interpolated or resampled"
            )
    return result
