import json
from pathlib import Path

import pytest

from datary.sessions import Session
from datary.utils import safe_name, safe_output


def test_path_traversal() -> None:
    with pytest.raises(ValueError):
        safe_name("../escape")
    with pytest.raises(ValueError):
        safe_output(Path.cwd(), Path("../escape"))


def test_malicious_manifest(tmp_path: Path) -> None:
    session = tmp_path / "bad"
    session.mkdir()
    (session / "records.jsonl").write_text("", encoding="utf-8")
    (session / "manifest.json").write_text(json.dumps({"session_format_version": "1", "session_name": "bad", "record_count": 0, "hashes": {"../x": "bad"}}), encoding="utf-8")
    assert Session.open(session).verify()[0].startswith("unsafe hash path")


def test_symlink_session_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError):
        Session.open(link)

