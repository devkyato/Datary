"""Write SHA-256 checksums for the current version's distribution artifacts."""
import hashlib
import re
from pathlib import Path


def current_version(pyproject: Path = Path("pyproject.toml")) -> str:
    text = pyproject.read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, re.MULTILINE)
    if match is None:
        raise ValueError("project version was not found in pyproject.toml")
    return match.group(1)


def main() -> int:
    distribution = Path("dist")
    version = current_version()
    artifacts = sorted(distribution.glob(f"datary_lab-{version}*"))
    artifacts = [path for path in artifacts if path.is_file()]
    if not artifacts:
        raise FileNotFoundError(f"no distribution artifacts found for version {version}")
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in artifacts
    ]
    (distribution / "SHA256SUMS").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
