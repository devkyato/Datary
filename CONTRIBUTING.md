# Contributing

Use Python 3.9 or newer, install `.[dev]`, and run:

```bash
pytest
ruff check .
mypy
python -m build
```

Add deterministic tests for behavioural changes. Do not add telemetry, network dependencies, data
execution, or backwards-incompatible session changes without documentation.

