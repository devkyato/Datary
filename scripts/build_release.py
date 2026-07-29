"""Build wheel and source distribution."""
import subprocess
import sys

raise SystemExit(subprocess.call([sys.executable, "-m", "build"]))

