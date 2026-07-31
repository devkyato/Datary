# Datary public release readiness

This document defines the path from a credible analytical alpha to a public tool that users can discover, understand, verify, and adopt safely.

## Positioning

Datary is a local-first terminal laboratory for recording, inspecting, comparing, replaying, plotting, and reporting structured experimental data. It should emphasize reproducibility, explicit assumptions, portable evidence, and offline use—not claim to replace notebooks, databases, or full scientific workflow platforms.

## Release blockers

- Verify session integrity before inspect, compare, replay, plot, or report operations by default.
- Add an explicit `--allow-unverified` forensic mode with permanent warnings in every output.
- Add deterministic bounded downsampling for very large plots and disclose original versus plotted point counts.
- Define comparison resampling and interpolation policies before allowing improvement percentages across different sample rates.
- Add optional detached signatures for authorship authenticity while preserving unsigned local sessions.

## Usability improvements

- Add `datary init` for a guided project/session template.
- Add `datary doctor` for session integrity, environment, optional plotting dependencies, schema, timestamps, and storage checks.
- Add `datary profile` commands for reusable named quality thresholds and domain bounds.
- Add `datary explain <finding-id>` with assumptions, evidence, confidence, and remediation.
- Add CSV, JSONL, and session preview commands that never mutate evidence.
- Add machine-readable JSON output consistently across commands.
- Add redaction profiles for fields containing names, emails, identifiers, locations, or secrets.

## Documentation site

Publish versioned guides for quickstart, session anatomy, supported inputs, integrity versus authenticity, timestamp handling, quality findings, control metrics, comparison assumptions, plotting, privacy, reproducibility, troubleshooting, and API usage. Include complete worked examples for sensors, network telemetry, control-system experiments, benchmarks, and classroom labs.

## Discoverability

Expand accurate search terms to include `experimental data`, `sensor data analysis`, `jsonl analysis`, `csv quality`, `reproducible experiments`, `offline data tool`, `time series inspection`, `telemetry analysis`, and `terminal data laboratory`. Add repository topics, social preview artwork, FAQ content based on common user questions, and reciprocal links among GitHub, the documentation site, PyPI, and releases.

## Publication targets

- PyPI for `datary-lab` using trusted publishing.
- GitHub Releases with wheel, sdist, checksums, SBOM, signatures, and example sessions.
- Read the Docs or GitHub Pages for versioned documentation.
- Optional conda-forge packaging only after the PyPI release stabilizes and dependencies remain reproducible.

## Release automation

A release tag should run Linux, Windows, and macOS tests; integrity checks on checked-in sessions; clean-wheel installation; hostile-input tests; memory checks; plot regression checks; reproducible build verification; SBOM creation; checksums; signatures; and documentation link validation.

## Success criteria

A new user should be able to install Datary, record a sample stream, verify the session, inspect findings, generate a report, understand every analytical assumption, and distinguish corruption detection from authorship verification without reading source code.