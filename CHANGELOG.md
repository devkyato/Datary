# Changelog

## Unreleased

## 0.2.5 - 2026-08-12

- Clarify overwrite conflicts with an explicit `--overwrite` hint.
- Reject `compare` invocations that provide fewer than two sources at the CLI.
- Update the bug-report version placeholder to 0.2.5.

## 0.2.4 - 2026-08-09

Publication and documentation quality release; runtime behaviour is unchanged.

- Replace the plain Zenodo summary with sanitizer-safe, structured HTML covering installation,
  use, applications, limitations, documentation, related software, and citation.
- Expand Citation File Format metadata and consistently identify the creator as
  `@dev.mako (devkyato)` of MATA Company.
- Synchronize package, runtime, archival, citation, README, and release-note versions.
- Add a documentation index and clearer README output, security, limitation, and connected-project
  guidance.
- Regenerate the deterministic noisy-sensor example with 0.2.4 metadata and valid integrity
  hashes.

## 0.2.3 - 2026-08-09

- Add Zenodo and Citation File Format metadata for archival citation.
- Refresh public release references for the 0.2.3 publication.

## 0.2.2 - 2026-08-08

Maintenance release focused on the public `/Datary` repository path and honest large-plot
handling.

- Point badges, package metadata, issue templates, and install links at
  `https://github.com/devkyato/Datary`.
- Add extrema-preserving plot downsampling with `--plot-max-points` (default 5000).
- Persist plot downsample metadata beside each PNG/SVG and surface it in CLI output and reports.
- Document the connected local-first and hardware projects maintained alongside Datary.

## 0.2.1 - 2026-07-29

Oh! The final post-publication check caught a platform detail worth fixing immediately: Git
normalizes checked-in text to LF, while Python's CSV writer defaulted to CRLF. That changed the
example session's `data.csv` bytes after its manifest hash had been generated.

- make every Datary CSV writer emit explicit LF line endings on every platform;
- regenerate the example session so its checked-in evidence verifies after a fresh clone; and
- add a byte-level regression assertion for recording CSV output.

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
