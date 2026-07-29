"""Verify deterministic generator output in separate calls."""
import subprocess
import sys

command = [sys.executable, "-m", "datary", "generate", "noisy-sensor", "--seed", "123"]
first = subprocess.check_output(command)
second = subprocess.check_output(command)
if first != second:
    raise SystemExit("generator output differs")
print("deterministic")

