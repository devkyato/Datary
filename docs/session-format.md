# Session format

New Datary 0.2 recordings use session format `2`. The reader also accepts format `1` sessions.
Unknown manifest keys should be ignored by compatible readers.

## Required files

| Path | Purpose |
|---|---|
| `manifest.json` | Identity, parser policy, schema, field roles, counts, privacy choices, commands, and artifact hashes |
| `manifest.sha256` | Lowercase SHA-256 digest of the exact `manifest.json` bytes |
| `raw.log` | Every input line received as text |
| `records.jsonl` | Valid JSON objects, one per line |
| `invalid.jsonl` | Rejected logical records with record number and reason |
| `data.csv` | Spreadsheet-safe convenience representation of valid records |
| `metrics.json` | General, timing, and requested engineering metrics |
| `quality.json` | Structured quality findings |
| `notes.md` | User-editable local notes |
| `plots/` | Generated PNG or SVG plots |
| `reports/` | Generated Markdown or JSON reports |

All text is UTF-8. JSON output rejects NaN and infinities. Start and end timestamps are ISO 8601
with timezone information.

## Integrity model

`manifest.json` contains SHA-256 digests for `raw.log`, `records.jsonl`, `invalid.jsonl`,
`data.csv`, `metrics.json`, `quality.json`, and `notes.md`. `manifest.sha256` covers the manifest.
Verification also parses the record files and compares their counts with the manifest.

Plots and reports are generated after recording and are not automatically added to the immutable
manifest. Editing `notes.md` intentionally changes its digest and will be reported by verification.

I want the boundary here to be unambiguous: this detects accidental corruption and incomplete
copies. It is not a digital signature. Someone able to rewrite the whole directory can also
rewrite every checksum.

## Publication and compatibility

A recording is assembled in a sibling staging directory. With `--overwrite`, the old directory is
renamed to a backup only after the replacement is complete; publication failure restores it.
Temporary analysis storage is never part of the published format.

Format 1 did not require `manifest.sha256`, did not hash every evidentiary artifact, and performed
less structural validation. Datary continues to open it so existing experiments are not stranded,
but new integrity guarantees apply only to format 2.
