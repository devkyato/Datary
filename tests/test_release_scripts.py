import runpy
from pathlib import Path

import pytest

from datary import __version__

SCRIPT = Path(__file__).parents[1] / "scripts" / "build_checksums.py"
current_version = runpy.run_path(str(SCRIPT), run_name="datary_checksum_test")["current_version"]


def test_current_release_version() -> None:
    assert current_version() == __version__


def test_missing_project_version_is_rejected(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'example'\n", encoding="utf-8")
    with pytest.raises(ValueError, match="project version"):
        current_version(pyproject)
