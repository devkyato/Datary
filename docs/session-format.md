# Session format

Format version `1` uses UTF-8 JSON/JSONL/CSV and ordinary directories. `manifest.json` is the source
of identity and includes timezone-aware start/end times, counts, fields, units, parser warnings,
privacy-safe provenance, commands, and SHA-256 hashes. `raw.log` is exact text; `records.jsonl`
contains valid objects; `invalid.jsonl` contains reasons. Unknown manifest keys should be ignored.

