![Datary — local-first terminal laboratory](docs/assets/datary-cover.png)

# Datary

[![CI](https://github.com/devkyato/Datary/actions/workflows/ci.yml/badge.svg)](https://github.com/devkyato/Datary/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/devkyato/Datary?include_prereleases)](https://github.com/devkyato/Datary/releases)
[![Python](https://img.shields.io/badge/Python-3.9--3.14-3776AB.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Datary is my local-first terminal laboratory for recording, validating, analysing, replaying,
comparing, plotting, and documenting data emitted by programs and simulations.

> Run a program, capture its output, validate the data, measure the behaviour, compare
> experiments, and generate reproducible evidence.

**Status:** `0.2.2` is an alpha. This release adds explicit plot downsampling metadata, moves the
canonical repository path to `/Datary`, and keeps the session reader compatible with format 1;
new recordings still use session format 2.

## Why I built it

I kept running small programs and simulations, then ending up with the same loose collection of
terminal output, one-off parsing scripts, screenshots, and notes. The program had run, but the
evidence around the run was fragile.

I thought about that point for a while: what if one command could preserve the original output,
parse what was valid, explain what looked wrong, calculate useful measurements, and leave enough
context to reproduce the experiment later? That became Datary.

Oh! One important boundary is that Datary does not try to become the experiment. It never executes
input, silently decides what “better” means, or claims that a clean report proves a sound
experiment. It records evidence and exposes the assumptions used to examine it.

## Install

Datary supports CPython 3.9–3.14. Core operation has no required runtime dependency; Matplotlib is
optional and uses the headless `Agg` backend.

```bash
python -m pip install https://github.com/devkyato/Datary/releases/download/v0.2.2/datary_lab-0.2.2-py3-none-any.whl
datary --version
```

For plotting:

```bash
python -m pip install "datary-lab[plot]"
```

For a local checkout:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
datary --version
```

On macOS or Linux, activate with `source .venv/bin/activate`.

## Five-minute local demonstration

```bash
datary generate noisy-sensor --seed 1 | datary record demo --format jsonl --time-field timestamp
datary inspect demo --quality
datary inspect demo --plot value
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

Datary reads standard input, CSV, TSV, incrementally decoded JSON arrays, JSON Lines,
whitespace-delimited rows, `key=value` rows, headerless comma streams (`--format stream`), and
existing Datary sessions. CSV supports quoted embedded newlines. UTF-8 BOMs are accepted.
Duplicate JSON keys and non-finite JSON numbers are rejected with evidence.

Detection is deliberately conservative. Empty or ambiguous input requires `--format`; Datary
never guesses merely to keep a pipeline moving.

For delimiter-based formats, the documented `conservative-scalars-v1` policy converts empty cells,
lowercase JSON booleans, canonical integers, and canonical finite floats. Identifier-like values
such as `00123` and tokens such as `NA` remain strings. The policy name is recorded in the
manifest.

## Session directory

Each recording is self-contained:

```text
demo/
|-- manifest.json       # identity, schema, options, commands, artifact hashes
|-- manifest.sha256     # corruption check for the manifest itself
|-- raw.log             # preserved input text
|-- records.jsonl       # accepted records
|-- invalid.jsonl       # rejected-record reasons
|-- data.csv            # spreadsheet-safe convenience export
|-- metrics.json
|-- quality.json
|-- notes.md
|-- plots/
`-- reports/
```

Recording uses a sibling staging directory. With `--overwrite`, the previous session is retained
until its complete replacement is ready; a failed recording restores the original. Without
`--overwrite`, an existing name receives a deterministic numeric suffix.

The ingest and analysis path is disk-backed and bounded by line, JSON-buffer, field, and file
limits rather than the number of records. Temporary SQLite is an implementation detail and is
removed before the session is published.

## Inspection, quality, and plots

```bash
datary inspect demo --field value
datary inspect demo --quality
datary inspect demo --plot value --plot-kind scatter --plot-format svg
datary inspect demo --monotonic-field distance --counter-field packet_count --quality
```

Checks cover missing and invalid values, duplicate rows and timestamps, time moving backwards,
irregular intervals, large gaps, shape and type changes, frozen and constant signals, spikes,
robust outliers, high relative noise, sequence loss, counter resets, and explicit monotonicity
expectations. Findings carry the check ID, severity, field, affected records, evidence, threshold,
explanation, assumptions, and a suggested investigation.

Zero-MAD signals and missing-value index positions are handled explicitly. Schema changes compare
field names, not only record length.

Plots support PNG and SVG line, scatter, step, and histogram output, with missing-data markers
where an x-position is available. User field names are sanitized before becoming filenames, plot
directories may not be symlinks, and existing plots require `--overwrite-plot`.

Very large plots use an explicit extrema-preserving bucket downsampler controlled by
`--plot-max-points` (default 5000). Canonical records are unchanged. Each plot writes a sibling
`.meta.json` file that records the algorithm, parameters, original point count, plotted point
count, missing-marker count, and whether global extrema were preserved. Inspection and reports
surface that metadata.

## Metrics and engineering roles

General metrics retain observation order for net change and adjacent differences while using a
separate sorted view for quantiles. They include count, missing count, extrema, mean, median,
sample variance, sample standard deviation, percentiles, sum, RMS, net rate of change, and mean
absolute adjacent difference.

Timing accepts numeric elapsed seconds or timezone-aware ISO 8601 timestamps. It reports interval
statistics, population jitter, effective sample rate, gaps, backwards time, and duplicate
timestamps—including non-adjacent duplicates.

Control and network metrics are opt-in because their field meanings cannot be inferred honestly:

```bash
python controller.py | datary record controller \
  --format jsonl \
  --time-field timestamp \
  --target-field target \
  --response-field response

python network.py | datary record network \
  --format jsonl \
  --time-field timestamp \
  --sequence-field sequence \
  --latency-field latency_ms \
  --bytes-field bytes
```

The field roles, definitions, assumptions, and warnings flow into inspection and reports. See
[the metric definitions](docs/metrics.md).

## Comparing experiments

```bash
datary compare baseline improved --field error --goal lower:error
datary compare run-1 run-2 run-3 --report comparison.md --format markdown
```

Fields align by name and output ordering is deterministic. Datary reports per-source count, range,
mean, median, standard deviation, declared units, sampling rates, individual time ranges, and the
shared range when available. Unit conflicts and non-overlapping time ranges block confident goal
claims.

I thought this part deserved a firm rule: without `--goal lower:FIELD` or
`--goal higher:FIELD`, Datary does not label an experiment better. Current alpha comparisons do
not interpolate or resample; differing rates are disclosed and block percentage-improvement
claims.

## Replay, reports, conversion, and generators

```bash
datary replay demo --speed 2
datary replay demo --no-timing --format csv
datary report demo --format json --output demo.json
datary convert readings.csv --to jsonl
datary generate pid-response --seed 7 --duration 20 --sample-rate 50
```

Replay preserves relative numeric or ISO 8601 timing unless `--no-timing` is selected. Virtual
replay remains available through the Python API and tests.

Markdown reports contain identity, reproduction commands, schema, statistics, timing,
engineering metrics, complete quality evidence, integrity status, hashes, assumptions, and links
to local plots. JSON reports contain the same structured evidence.

CSV convenience exports neutralize formula-like strings and headers with a leading apostrophe;
canonical values remain unchanged in `records.jsonl`. Conversion writes an invalid-record sidecar
rather than silently discarding malformed input.

Profiles are `sine`, `noisy-sensor`, `frozen-sensor`, `missing-samples`,
`duplicate-samples`, `pid-response`, `motor-speed`, `battery-drain`, `network-latency`, and
`packet-loss`. Equal profile, seed, options, and Datary version produce identical records. Profile
defaults create their named anomaly, while an explicit `--missing-rate 0` or
`--duplicate-rate 0` is honoured exactly.

## Typed Python API

```python
from datary import Session, compare_sessions, inspect_source

session = Session.open("demo")
summary = inspect_source(session)
comparison = compare_sessions(
    ["baseline", "improved"],
    fields=["error", "response"],
)
```

Only `Session`, `inspect_source`, and `compare_sessions` are stable public names during the alpha.
Record values use a recursive JSON type rather than unrestricted Python objects.

## Reproducibility, privacy, and security

Absolute working paths are `<redacted>` unless `--include-path` is supplied. Environment values
are never copied. Datary has no telemetry, background service, or network call.

SHA-256 covers the manifest and every recording-time evidentiary file, including rejected records
and notes. Plots and reports are derived later and are not silently added to the immutable
recording manifest. These checks detect accidental corruption; they are not signatures and do not
prove authenticity against an attacker who can rewrite the entire session.

Input remains inert. There is no expression evaluation, command expansion, pickle loading, or
formula execution. Session and output paths reject traversal and symlink redirection in trusted
locations; terminal and Markdown output escape untrusted control or markup content.

Read [reproducibility](docs/reproducibility.md), [privacy](docs/privacy.md), and
[security policy](SECURITY.md) before sharing sensitive sessions.

## Honest limitations

Datary is not:

- a spreadsheet application;
- a replacement for statistical or domain expertise;
- a cloud observability platform;
- a guarantee that collected data is scientifically valid; or
- a substitute for properly designed experiments.

The alpha does not authenticate session authorship, automatically infer physical unit
conversions, interpolate comparison series, or decide domain-specific thresholds. Plotting can
still materialize selected records for Matplotlib before downsampling to `--plot-max-points`.
JSON array decoding is incremental but one pending JSON value is capped at 16 MiB.

## Connected projects

These repositories form the surrounding toolkit I maintain alongside Datary:

| Project | Role |
| --- | --- |
| **[Datary](https://github.com/devkyato/Datary)** | Local-first terminal laboratory for reproducible program and simulation evidence |
| **[Lowpack](https://github.com/devkyato/Lowpack)** | Local-first, application-aware lossless packing |
| **[Relay](https://github.com/devkyato/Relay)** | Local-first timing-risk source review for control programs |
| **[OpenNet](https://github.com/devkyato/OpenNet)** | Typed ONP/1 messaging for ESP32, Raspberry Pi, and backends |
| **[TapAuth](https://github.com/devkyato/TapAuth)** | Raspberry Pi NFC attendance and reservation kiosk |
| **[Custom Arduino Libraries](https://github.com/devkyato/Custom-Arduino-Libraries)** | Non-blocking LED and digital-output patterns |
| **[Arduino Programs Guide](https://github.com/devkyato/Arduino-Programs-Guide)** | Safety-first, compile-checked Arduino Uno course |

## Contributing and licence

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m build
```

If the workflow sounds useful, I would be glad to have another set of eyes on it. Please include
deterministic regression tests and explain the mathematical or security assumption behind a
change. See [CONTRIBUTING.md](CONTRIBUTING.md).

Datary is MIT-licensed; copyright © 2026 devkyato.
