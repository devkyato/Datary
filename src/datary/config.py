"""Configuration defaults."""

from __future__ import annotations

import os
from pathlib import Path


def default_workspace() -> Path:
    configured = os.environ.get("DATARY_WORKSPACE")
    if configured:
        return Path(configured).expanduser()
    return Path.cwd()


SESSION_FORMAT_VERSION = "2"
SUPPORTED_SESSION_FORMAT_VERSIONS = ("1", "2")
MAX_AUTO_DETECT_BYTES = 262_144
LARGE_FILE_WARNING_BYTES = 1_000_000_000
