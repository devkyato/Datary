# Contributing

I built Datary around a small promise: input remains inert, evidence stays local, and every result
should be explainable. If you contribute, please help me keep that promise.

Use Python 3.9 or newer, install `.[dev]`, and run:

```bash
pytest
ruff check .
mypy
python -m build
```

Add deterministic tests for behavioural changes. If a quality rule needs a threshold, explain the
assumption and show the evidence behind its finding.

Please do not add telemetry, background network dependencies, data execution, or
backwards-incompatible session changes without an explicit design discussion and documentation.
