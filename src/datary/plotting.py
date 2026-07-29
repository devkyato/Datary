"""Headless Matplotlib plots."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence

from datary.models import Record
from datary.utils import finite_number


def create_plot(
    records: Sequence[Record],
    fields: Sequence[str],
    output: Path,
    *,
    time_field: Optional[str] = None,
    kind: str = "line",
    overwrite: bool = False,
) -> Path:
    if output.exists() and not overwrite:
        raise FileExistsError(output)
    if output.suffix.lower() not in {".png", ".svg"}:
        raise ValueError("plot output must use .png or .svg")
    import matplotlib

    matplotlib.use("Agg", force=True)
    from matplotlib import pyplot as plt

    figure, axis = plt.subplots(figsize=(8, 4.5))
    for field in fields:
        points = [(index, finite_number(record.get(field))) for index, record in enumerate(records)]
        x_values: List[float] = []
        y_values: List[float] = []
        for index, value in points:
            x = finite_number(records[index].get(time_field)) if time_field else float(index)
            if x is not None and value is not None:
                x_values.append(x)
                y_values.append(value)
        if kind == "scatter":
            axis.scatter(x_values, y_values, s=10, label=field)
        elif kind == "step":
            axis.step(x_values, y_values, where="post", label=field)
        elif kind == "histogram":
            axis.hist(y_values, alpha=0.5, label=field)
        else:
            axis.plot(x_values, y_values, label=field)
    axis.set_xlabel(time_field or "record")
    axis.grid(True, alpha=0.25)
    axis.legend()
    figure.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output)
    plt.close(figure)
    return output

