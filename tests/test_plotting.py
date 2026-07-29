from pathlib import Path

import pytest

from datary.plotting import create_plot


def test_png_and_svg(tmp_path: Path) -> None:
    records = [{"t": 0, "x": 1}, {"t": 1, "x": 2}]
    for suffix in (".png", ".svg"):
        output = create_plot(records, ["x"], tmp_path / f"plot{suffix}", time_field="t")
        assert output.stat().st_size > 100
        with pytest.raises(FileExistsError):
            create_plot(records, ["x"], output)

