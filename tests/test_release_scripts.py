from pathlib import Path

import pytest
from scripts.build_checksums import current_version


def test_current_release_version() -> None:
    assert current_version() == "0.1.2"


def test_missing_project_version_is_rejected(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'example'\n", encoding="utf-8")
    with pytest.raises(ValueError, match="project version"):
        current_version(pyproject)
