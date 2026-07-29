# Privacy

I wanted a session to be shareable without quietly publishing the shape of someone's laptop.
Working-directory paths are therefore `<redacted>` by default. Use `--include-path` only when that
provenance is intentionally part of the record.

Datary does not copy environment variables, send telemetry, start a background service, or make
network calls. The workspace is an ordinary directory selected by `DATARY_WORKSPACE` or
`--workspace`.

Oh! Raw capture is intentionally faithful, so it can contain credentials, personal data, device
identifiers, or secrets printed by the producer. Hashes do not anonymize data, and reports can
repeat field names or values. Review permissions and redact a copy—not the original evidence—before
sharing.

User-supplied commands and parameters are included only when explicitly passed. CSV exports
neutralize spreadsheet formulas, but privacy review is still required before opening or sending
them.
