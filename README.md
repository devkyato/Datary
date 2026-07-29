![Datary — local-first terminal laboratory](docs/assets/datary-cover.png)

# Datary

[![CI](https://github.com/devkyato/datary-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/devkyato/datary-lab/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/devkyato/datary-lab?include_prereleases)](https://github.com/devkyato/datary-lab/releases)
[![Python](https://img.shields.io/badge/Python-3.9--3.14-3776AB.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Datary is my local-first terminal laboratory for recording, validating, analysing, replaying,
comparing, plotting, and documenting data emitted by programs and simulations.

> Run a program, capture its output, validate the data, measure the behaviour, compare
> experiments, and generate reproducible evidence.

**Status:** `0.1.3` is an honest alpha. Session format changes will be documented, but may not
remain backward compatible before 1.0.

## Why I built it

I kept running small programs and simulations, then ending up with the same loose collection of
terminal output, one-off parsing scripts, screenshots, and notes. The program had run, but the
evidence around the run was fragile.

I thought about that point for a while: what if one command could preserve the original output,
parse what was valid, explain what looked wrong, calculate useful measurements, and leave behind
enough context to reproduce the experiment later? That became Datary.

Oh! One important part is that Datary does not try to become the experiment. It does not execute
input files, decide whether your scientific method is sound, or quietly call one result “better.”
It records the evidence and gives you transparent tools for examining it.

## How I think about a run

A Datary workflow is deliberately small:

1. Your program writes data to standard output or an ordinary file.
2. Datary preserves the raw input before interpreting it.
3. Valid records become clean JSON Lines and CSV; malformed input keeps an explanation.
4. Metrics and quality checks describe what happened and state their assumptions.
5. The session keeps the hashes, commands, reports, plots, and notes together.

That is the whole idea: the next person looking at the result—even when that person is future
you—should be able to follow the trail from raw output to reported evidence.

## Install

Datary supports Python 3.9–3.14 and has no required runtime dependency. Matplotlib is optional.

Install the current GitHub release:

```bash
python -m pip install https://github.com/devkyato/datary-lab/releases/download/v0.1.3/datary_lab-0.1.3-py3-none-any.whl
datary --version
```

Or work from a local checkout:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
datary --version
```

## Five-minute local demonstration

```bash
datary generate noisy-sensor --seed 1 | datary record demo --format jsonl --time-field timestamp
datary inspect demo --quality
datary report demo
datary replay demo --no-timing
datary compare demo demo --field value
```

Set `DATARY_WORKSPACE` or pass `--workspace PATH` before the subcommand. Nothing is uploaded,
tracked, or executed from input.

## Capture and supported formats

```bash
python motor_sim.py | datary record motor-baseline --time-field timestamp
python network_test.py | datary record latency-test --format jsonl
datary inspect measurements.csv
datary inspect readings.jsonl
datary convert readings.jsonl --to csv
```

Datary reads stdin, CSV, TSV, JSON arrays, JSON Lines, whitespace numeric rows, `key=value`
rows, headerless comma streams (`--format stream`), and existing sessions. Detection is
conservative: ambiguous or empty input requires `--format`. Inputs are inert data—never code.

## Session directory

Each recording is self-contained. I chose ordinary files here on purpose: you can inspect,
copy, archive, or version a session without a Datary server.

```text
demo/
|-- manifest.json     # identity, schema, hashes, commands, privacy choices
|-- raw.log           # exact source text
|-- records.jsonl     # clean records
|-- invalid.jsonl     # malformed-record reasons
|-- data.csv
|-- metrics.json
|-- quality.json
|-- notes.md
|-- plots/
`-- reports/
```

Existing names receive a deterministic numeric suffix; `--overwrite` is explicit. Absolute
working paths are redacted unless `--include-path` is used. Environment values are never stored.

## Inspection, quality, and plots

```bash
datary inspect demo --field value
datary inspect demo --quality
datary inspect demo --plot value
datary inspect demo --monotonic-field distance --counter-field packet_count --quality
```

Checks cover missing/non-finite values, duplicates, changing shapes and types, frozen or
constant signals, spikes, robust outliers, high noise, backwards/duplicate timestamps,
irregular intervals, gaps, sequence loss, counter resets, and explicit monotonicity expectations.
Findings include evidence, thresholds, assumptions, explanations, and suggested investigation.
I treat them as leads to investigate, not verdicts.

Matplotlib uses the non-interactive `Agg` backend. The Python plotting API creates PNG or SVG
line, scatter, step, and histogram plots without opening windows.

## Metrics and comparison

General metrics include count, missing count, extrema, mean, median, variance, standard
deviation, percentiles, sum, RMS, rate of change, and mean absolute difference. Timing metrics
include intervals, jitter, effective sampling rate, gaps, and duplicate timestamps. The public
module also implements defined control-response and network metrics; see
[docs/metrics.md](docs/metrics.md).

```bash
datary compare baseline improved --field error --goal lower:error
datary compare run-1 run-2 run-3 --report comparison.md --format markdown
```

Fields are aligned by name and ordered deterministically. I thought this part deserved a firm
rule: Datary does not call an experiment better without an explicit goal. Incomparable fields
produce warnings instead of a confident-looking guess.

## Replay, reports, and generators

```bash
datary replay demo --speed 2
datary report demo --format json --output demo.json
datary generate pid-response --seed 7 --duration 20 --sample-rate 50
```

Profiles: `sine`, `noisy-sensor`, `frozen-sensor`, `missing-samples`,
`duplicate-samples`, `pid-response`, `motor-speed`, `battery-drain`,
`network-latency`, and `packet-loss`. Equal profile, seed, and options produce identical output.

## Python API

```python
from datary import Session, compare_sessions, inspect_source

session = Session.open("demo")
summary = inspect_source(session)
comparison = compare_sessions(["baseline", "improved"], fields=["error", "response"])
```

Only these names are the stable public API in this alpha.

## Reproducibility, privacy, and security

Raw input, clean records, invalid reasons, configuration, exact follow-up commands, timezone-aware
timestamps, and SHA-256 hashes remain together. Critical JSON is written atomically. Limits apply
to line size and field count. Session manifests cannot escape through hash paths, symlinks are
rejected for trusted session artifacts, reports never interpret formulas or commands, and there
are no background network calls. See [reproducibility](docs/reproducibility.md),
[privacy](docs/privacy.md), and [SECURITY.md](SECURITY.md).

## Limitations

Datary is not a spreadsheet application, a replacement for statistical expertise, a cloud
observability platform, a guarantee that collected data is scientifically valid, or a substitute
for properly designed experiments. The alpha currently keeps valid records in memory for final
whole-session statistics after streaming them to disk; input ingestion itself is bounded per line.
Timestamp parsing currently expects numeric elapsed time for timing analysis and replay.

I would rather state those limits plainly than hide them behind an alpha label. The open issues
track the work needed to remove them.

## Contributing and licence

If the workflow sounds useful, I would be glad to have another set of eyes on it. Run `pytest`,
`ruff check .`, and `mypy`, then see [CONTRIBUTING.md](CONTRIBUTING.md). Datary is MIT-licensed;
copyright © 2026 devkyato.
