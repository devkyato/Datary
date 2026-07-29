"""Headless Matplotlib plots."""

from __future__ import annotations

import importlib
import os
import tempfile
from pathlib import Path
from typing import Any, List, Optional, Sequence

from datary.models import Record
from datary.utils import finite_number, temporal_number


def create_plot(
    records: Sequence[Record],
    fields: Sequence[str],
    output: Path,
    *,
    time_field: Optional[str] = None,
    kind: str = "line",
    overwrite: bool = False,
) -> Path:
    if output.is_symlink():
        raise ValueError("plot output may not be a symbolic link")
    if output.exists() and not overwrite:
        raise FileExistsError(output)
    if output.suffix.lower() not in {".png", ".svg"}:
        raise ValueError("plot output must use .png or .svg")
    if kind not in {"line", "scatter", "step", "histogram"}:
        raise ValueError("plot kind must be line, scatter, step, or histogram")
    matplotlib: Any = importlib.import_module("matplotlib")
    matplotlib.use("Agg", force=True)
    plt: Any = importlib.import_module("matplotlib.pyplot")

    figure, axis = plt.subplots(figsize=(8, 4.5))
    plotted = 0
    for field in fields:
        if not any(field in record for record in records):
            continue
        points = [(index, finite_number(record.get(field))) for index, record in enumerate(records)]
        x_values: List[float] = []
        y_values: List[float] = []
        missing_x: List[float] = []
        for index, value in points:
            x = temporal_number(records[index].get(time_field)) if time_field else float(index)
            if x is not None and value is not None:
                x_values.append(x)
                y_values.append(value)
            elif x is not None:
                missing_x.append(x)
        if kind == "scatter":
            axis.scatter(x_values, y_values, s=10, label=field)
        elif kind == "step":
            axis.step(x_values, y_values, where="post", label=field)
        elif kind == "histogram":
            axis.hist(y_values, alpha=0.5, label=field)
        else:
            axis.plot(x_values, y_values, label=field)
        if missing_x and kind != "histogram":
            marker_y = min(y_values) if y_values else 0.0
            axis.scatter(
                missing_x,
                [marker_y] * len(missing_x),
                marker="x",
                s=24,
                label=f"{field} missing",
            )
        plotted += len(y_values) + (len(missing_x) if kind != "histogram" else 0)
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
    return output
