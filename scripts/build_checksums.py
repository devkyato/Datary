"""Write SHA-256 checksums for dist artifacts."""
import hashlib
from pathlib import Path

lines = []
for path in sorted(Path("dist").glob("*")):
    if path.is_file() and path.name != "SHA256SUMS":
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
Path("dist/SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")

