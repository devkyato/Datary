"""Deterministic, honest experiment comparison."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from datary.inspection import inspect_source
from datary.models import Comparison


def compare_sessions(
    sources: Sequence[Union[str, Path]],
    fields: Optional[Sequence[str]] = None,
    goal: Optional[str] = None,
) -> Comparison:
    if len(sources) < 2:
        raise ValueError("comparison requires at least two sources")
    inspections = [inspect_source(source) for source in sources]
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
    result: Dict[str, Dict[str, Any]] = {}
    for field in selected:
        means = {
            str(source): inspections[index].metrics[field].get("mean")
            for index, source in enumerate(sources)
        }
        detail: Dict[str, Any] = {"means": means}
        baseline = next(iter(means.values()))
        if field == goal_field and baseline not in (None, 0):
            improvements: Dict[str, Optional[float]] = {}
            for name, value in means.items():
                if value is None:
                    improvements[name] = None
                elif direction == "lower":
                    improvements[name] = (baseline - value) / abs(baseline) * 100
                else:
                    improvements[name] = (value - baseline) / abs(baseline) * 100
            detail["improvement_percent_vs_first"] = improvements
        result[field] = detail
    if goal_field and goal_field not in result:
        warnings.append(f"goal field {goal_field!r} is not comparable")
    if not goal:
        warnings.append("no comparison goal supplied; no experiment is labelled better")
    return Comparison([str(source) for source in sources], result, warnings, goal)
