# Contributing

I built Datary around a small promise: input remains inert, evidence stays local, and every result
should be explainable. If you contribute, please help me keep that promise.

Use a supported Python version and install the development extras:

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m build
```

Behavioural changes need deterministic tests. Mathematical changes need a definition, an ordered
counterexample where relevant, and a statement of assumptions. Security changes need a regression
test for the boundary: traversal, symlink, failed publication, malicious manifest, control
sequence, or formula-like export data.

Please do not add telemetry, background networking, data execution, or an always-on database.
Discuss session-format changes explicitly and keep older readers in mind.
