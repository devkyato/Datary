import importlib
from pathlib import Path
from typing import Any

import pytest

from datary.models import Record
from datary.plotting import create_plot


def test_png_and_svg(tmp_path: Path) -> None:
    records: list[Record] = [{"t": 0, "x": 1}, {"t": 1, "x": 2}]
    for suffix in (".png", ".svg"):
        output = create_plot(records, ["x"], tmp_path / f"plot{suffix}", time_field="t")
        assert output.stat().st_size > 100
        with pytest.raises(FileExistsError):
            create_plot(records, ["x"], output)
    matplotlib: Any = importlib.import_module("matplotlib")
    assert str(matplotlib.get_backend()).lower() == "agg"
