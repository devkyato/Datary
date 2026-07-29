# Changelog

## 0.2.0 - 2026-07-29

I treated this release as a corrective audit rather than a feature polish. A hard external review
showed that several green tests were confirming the old implementation instead of independently
checking its scientific and security claims.

- Preserved observation order for change metrics and added ordered counterexamples.
- Replaced whole-session recorder and inspector lists with exact disk-backed analysis.
- Made overwrite publication recoverable so a failed replacement keeps the prior session.
- Closed plot traversal and session symlink gaps; hardened manifests, record readers, terminal
  output, Markdown, CSV formulas, and generated-file publication.
- Added incremental JSON-array parsing, RFC-style multiline CSV, BOM handling, duplicate-key
  rejection, conservative scalar coercion, and non-finite-value evidence.
- Expanded integrity to rejected records, notes, structural counts, and the manifest itself while
  documenting that checksums are not authentication.
- Corrected frozen-value positions, same-length schema detection, zero-MAD outliers/spikes, and
  global duplicate timestamps.
- Added numeric and timezone-aware ISO 8601 timing, explicit engineering field roles, trapezoidal
  control integrals, network throughput, unit-aware comparisons, shared time ranges, and honest
  non-resampling warnings.
- Expanded Markdown reports, generator option semantics, Python 3.9 strict typing, adversarial
  regression coverage, and Windows/macOS CI smoke tests.
- Introduced session format 2 while retaining format 1 reading compatibility.

## 0.1.3 - 2026-07-29

- Rewrote the project story and workflow in a clearer, more personal voice.
- Added a narrative explanation of why Datary exists and how a recording becomes evidence.
- Refined architecture, reproducibility, privacy, tutorial, and contribution guidance.
- Updated installation and alpha-status references for the current release.

## 0.1.2 - 2026-07-29

- Added configurable monotonicity-violation and counter-reset quality checks.
- Exposed repeatable `--monotonic-field` and `--counter-field` inspection options.
- Added typed API parameters, deterministic findings, tests, and quality-check documentation.

## 0.1.1 - 2026-07-29

- Added canonical project, documentation, issue, and changelog metadata to distributions.
- Added repository status badges and automated package/runtime version consistency coverage.
- Preserved the Python 3.9 Markdown report compatibility fix in the release lineage.

## 0.1.0 - 2026-07-29

- Initial alpha with recording, inspection, comparison, replay, reports, conversion,
  deterministic generators, headless plots, integrity verification, and typed Python API.
