import importlib
import json
from pathlib import Path
from typing import Any

import pytest

from datary.models import Record
from datary.plotting import create_plot


def test_png_and_svg(tmp_path: Path) -> None:
    records: list[Record] = [{"t": 0, "x": 1}, {"t": 1, "x": 2}]
    for suffix in (".png", ".svg"):
        result = create_plot(records, ["x"], tmp_path / f"plot{suffix}", time_field="t")
        assert result.path.stat().st_size > 100
        assert result.metadata_path.is_file()
        with pytest.raises(FileExistsError):
            create_plot(records, ["x"], result.path)
    matplotlib: Any = importlib.import_module("matplotlib")
    assert str(matplotlib.get_backend()).lower() == "agg"


def test_extrema_preserving_downsample(tmp_path: Path) -> None:
    records: list[Record] = [{"t": index, "x": float(index)} for index in range(1_000)]
    records[100]["x"] = -500.0
    records[700]["x"] = 9_999.0
    result = create_plot(
        records,
        ["x"],
        tmp_path / "large.png",
        time_field="t",
        max_points=50,
    )
    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    downsample = metadata["downsample"]
    assert downsample["applied"] is True
    assert downsample["algorithm"] == "extrema-preserving-buckets"
    assert downsample["original_point_count"] == 1_000
    assert downsample["plotted_point_count"] <= 50
    assert downsample["preserved_global_extrema"] is True
    field_summary = downsample["parameters"]["fields"][0]
    assert field_summary["global_minimum"] == -500.0
    assert field_summary["global_maximum"] == 9_999.0


def test_missing_markers_survive_downsample(tmp_path: Path) -> None:
    records: list[Record] = []
    for index in range(200):
        if index % 17 == 0:
            records.append({"t": index, "x": None})
        else:
            records.append({"t": index, "x": float(index)})
    result = create_plot(
        records,
        ["x"],
        tmp_path / "missing.png",
        time_field="t",
        max_points=40,
    )
    downsample = result.downsample
    assert downsample.missing_marker_count > 0
    assert downsample.preserved_global_extrema is True
