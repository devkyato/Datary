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

## Release checklist

1. Bump `version` in `pyproject.toml` and `__version__` in `src/datary/__init__.py`.
2. Update `CHANGELOG.md` and add `docs/releases/X.Y.Z.md`.
3. Run the local checks above, then `python -m build` and `python scripts/build_checksums.py`.
4. Publish GitHub Release `vX.Y.Z` with the wheel, sdist, and `SHA256SUMS`.
5. Verify install from the release URL and `datary --version`.

The distribution package name remains `datary-lab`; the canonical repository path is
[`/Datary`](https://github.com/devkyato/Datary).
