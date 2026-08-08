"""Headless Matplotlib plots with explicit extrema-preserving downsampling."""

from __future__ import annotations

import importlib
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from datary.config import DEFAULT_PLOT_MAX_POINTS
from datary.models import Record
from datary.utils import atomic_json, finite_number, temporal_number

DOWNSAMPLE_ALGORITHM = "extrema-preserving-buckets"


@dataclass(frozen=True)
class PlotDownsampleInfo:
    algorithm: str
    max_points: int
    original_point_count: int
    plotted_point_count: int
    missing_marker_count: int
    preserved_global_extrema: bool
    applied: bool
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlotResult:
    path: Path
    metadata_path: Path
    fields: Tuple[str, ...]
    kind: str
    time_field: Optional[str]
    downsample: PlotDownsampleInfo

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": str(self.path),
            "metadata_path": str(self.metadata_path),
            "fields": list(self.fields),
            "kind": self.kind,
            "time_field": self.time_field,
            "downsample": self.downsample.to_dict(),
        }


def create_plot(
    records: Sequence[Record],
    fields: Sequence[str],
    output: Path,
    *,
    time_field: Optional[str] = None,
    kind: str = "line",
    overwrite: bool = False,
    max_points: int = DEFAULT_PLOT_MAX_POINTS,
) -> PlotResult:
    if output.is_symlink():
        raise ValueError("plot output may not be a symbolic link")
    if output.exists() and not overwrite:
        raise FileExistsError(output)
    if output.suffix.lower() not in {".png", ".svg"}:
        raise ValueError("plot output must use .png or .svg")
    if kind not in {"line", "scatter", "step", "histogram"}:
        raise ValueError("plot kind must be line, scatter, step, or histogram")
    if max_points < 2:
        raise ValueError("plot max_points must be at least 2")
    matplotlib: Any = importlib.import_module("matplotlib")
    matplotlib.use("Agg", force=True)
    plt: Any = importlib.import_module("matplotlib.pyplot")

    figure, axis = plt.subplots(figsize=(8, 4.5))
    plotted = 0
    field_summaries: List[Dict[str, Any]] = []
    total_original = 0
    total_plotted = 0
    total_missing = 0
    any_applied = False
    preserved_extrema = True

    for field_name in fields:
        if not any(field_name in record for record in records):
            continue
        series = _extract_series(records, field_name, time_field)
        original_count = len(series.x_values) + len(series.missing_x)
        total_original += original_count
        selected_x, selected_y, downsample_meta = _downsample_series(
            series.x_values,
            series.y_values,
            max_points=max_points,
            kind=kind,
        )
        missing_x = series.missing_x
        if kind != "histogram" and len(missing_x) > max_points:
            missing_x = _evenly_spaced(missing_x, max_points)
        any_applied = (
            any_applied or downsample_meta["applied"] or len(missing_x) < len(series.missing_x)
        )
        preserved_extrema = preserved_extrema and downsample_meta["preserved_global_extrema"]
        total_plotted += len(selected_y)
        total_missing += len(missing_x) if kind != "histogram" else 0

        if kind == "scatter":
            axis.scatter(selected_x, selected_y, s=10, label=field_name)
        elif kind == "step":
            axis.step(selected_x, selected_y, where="post", label=field_name)
        elif kind == "histogram":
            axis.hist(selected_y, alpha=0.5, label=field_name)
        else:
            axis.plot(selected_x, selected_y, label=field_name)
        if missing_x and kind != "histogram":
            marker_y = min(selected_y) if selected_y else 0.0
            axis.scatter(
                missing_x,
                [marker_y] * len(missing_x),
                marker="x",
                s=24,
                label=f"{field_name} missing",
            )
        plotted += len(selected_y) + (len(missing_x) if kind != "histogram" else 0)
        field_summaries.append(
            {
                "field": field_name,
                "original_point_count": original_count,
                "plotted_point_count": len(selected_y),
                "missing_marker_count": len(missing_x) if kind != "histogram" else 0,
                "original_missing_marker_count": len(series.missing_x)
                if kind != "histogram"
                else 0,
                "preserved_global_extrema": downsample_meta["preserved_global_extrema"],
                "global_minimum": downsample_meta["global_minimum"],
                "global_maximum": downsample_meta["global_maximum"],
            }
        )

    if not fields:
        plt.close(figure)
        raise ValueError("at least one plot field is required")
    if plotted == 0:
        plt.close(figure)
        raise ValueError("selected plot fields contain no numeric values")
    axis.set_xlabel(time_field or "record")
    axis.grid(True, alpha=0.25)
    axis.legend()
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.stem}.rendering-",
        suffix=output.suffix,
        dir=str(output.parent),
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        figure.tight_layout()
        figure.savefig(temporary)
        if output.exists() and not overwrite:
            raise FileExistsError(output)
        os.replace(temporary, output)
    finally:
        plt.close(figure)
        temporary.unlink(missing_ok=True)

    downsample = PlotDownsampleInfo(
        algorithm=DOWNSAMPLE_ALGORITHM,
        max_points=max_points,
        original_point_count=total_original,
        plotted_point_count=total_plotted + total_missing,
        missing_marker_count=total_missing,
        preserved_global_extrema=preserved_extrema,
        applied=any_applied,
        parameters={
            "kind": kind,
            "bucket_policy": "keep first, last, local min, and local max per bucket",
            "fields": field_summaries,
        },
    )
    metadata_path = output.with_suffix(output.suffix + ".meta.json")
    if metadata_path.is_symlink():
        raise ValueError("plot metadata may not be a symbolic link")
    if metadata_path.exists() and not overwrite:
        raise FileExistsError(metadata_path)
    result = PlotResult(
        path=output,
        metadata_path=metadata_path,
        fields=tuple(fields),
        kind=kind,
        time_field=time_field,
        downsample=downsample,
    )
    atomic_json(metadata_path, result.to_dict())
    return result


@dataclass
class _Series:
    x_values: List[float]
    y_values: List[float]
    missing_x: List[float]


def _extract_series(
    records: Sequence[Record], field_name: str, time_field: Optional[str]
) -> _Series:
    x_values: List[float] = []
    y_values: List[float] = []
    missing_x: List[float] = []
    for index, record in enumerate(records):
        value = finite_number(record.get(field_name))
        x = temporal_number(record.get(time_field)) if time_field else float(index)
        if x is None:
            continue
        if value is None:
            if field_name in record:
                missing_x.append(x)
            continue
        x_values.append(x)
        y_values.append(value)
    return _Series(x_values=x_values, y_values=y_values, missing_x=missing_x)


def _downsample_series(
    x_values: Sequence[float],
    y_values: Sequence[float],
    *,
    max_points: int,
    kind: str,
) -> Tuple[List[float], List[float], Dict[str, Any]]:
    count = len(y_values)
    if count == 0:
        return (
            [],
            [],
            {
                "applied": False,
                "preserved_global_extrema": True,
                "global_minimum": None,
                "global_maximum": None,
            },
        )
    global_minimum = min(y_values)
    global_maximum = max(y_values)
    if kind == "histogram":
        # Histograms only need values; keep extrema and evenly spaced body samples.
        if count <= max_points:
            return (
                list(x_values),
                list(y_values),
                {
                    "applied": False,
                    "preserved_global_extrema": True,
                    "global_minimum": global_minimum,
                    "global_maximum": global_maximum,
                },
            )
        selected_y = _evenly_spaced(list(y_values), max_points)
        if global_minimum not in selected_y:
            selected_y[0] = global_minimum
        if global_maximum not in selected_y:
            selected_y[-1] = global_maximum
        return (
            list(range(len(selected_y))),
            selected_y,
            {
                "applied": True,
                "preserved_global_extrema": True,
                "global_minimum": global_minimum,
                "global_maximum": global_maximum,
            },
        )

    if count <= max_points:
        return (
            list(x_values),
            list(y_values),
            {
                "applied": False,
                "preserved_global_extrema": True,
                "global_minimum": global_minimum,
                "global_maximum": global_maximum,
            },
        )

    # Reserve room for first/last anchors; remaining budget is shared across buckets.
    usable = max(max_points, 4)
    bucket_count = max(1, (usable - 2) // 2)
    selected_indices = _bucket_extrema_indices(y_values, bucket_count)
    selected_indices.add(0)
    selected_indices.add(count - 1)
    # Guarantee global extrema survive even when a bucket collapses them.
    selected_indices.add(y_values.index(global_minimum))
    selected_indices.add(len(y_values) - 1 - y_values[::-1].index(global_maximum))
    ordered = sorted(selected_indices)
    if len(ordered) > max_points:
        # Prefer anchors and extrema, then fill remaining slots evenly from the rest.
        required = {
            0,
            count - 1,
            y_values.index(global_minimum),
            len(y_values) - 1 - y_values[::-1].index(global_maximum),
        }
        remaining_budget = max_points - len(required)
        extras = [index for index in ordered if index not in required]
        if remaining_budget <= 0:
            ordered = sorted(required)[:max_points]
        else:
            ordered = sorted(required | set(_evenly_spaced(extras, remaining_budget)))

    selected_x = [x_values[index] for index in ordered]
    selected_y = [y_values[index] for index in ordered]
    return (
        selected_x,
        selected_y,
        {
            "applied": True,
            "preserved_global_extrema": global_minimum in selected_y
            and global_maximum in selected_y,
            "global_minimum": global_minimum,
            "global_maximum": global_maximum,
        },
    )


def _bucket_extrema_indices(values: Sequence[float], bucket_count: int) -> set[int]:
    count = len(values)
    if count == 0 or bucket_count <= 0:
        return set()
    selected: set[int] = set()
    for bucket in range(bucket_count):
        start = (bucket * count) // bucket_count
        end = ((bucket + 1) * count) // bucket_count
        if start >= end:
            continue
        segment = values[start:end]
        selected.add(start + segment.index(min(segment)))
        selected.add(start + (len(segment) - 1 - segment[::-1].index(max(segment))))
        selected.add(start)
        selected.add(end - 1)
    return selected


def _evenly_spaced(values: Sequence[Any], maximum: int) -> List[Any]:
    if len(values) <= maximum:
        return list(values)
    if maximum == 1:
        return [values[0]]
    return [values[round(index * (len(values) - 1) / (maximum - 1))] for index in range(maximum)]
