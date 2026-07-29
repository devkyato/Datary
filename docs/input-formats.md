# Input formats

Supported identifiers are `csv`, `tsv`, `json`, `jsonl`, `whitespace`, `keyvalue`, and `stream`.
CSV/TSV require a unique non-empty header. JSON is an array of objects; JSONL is one object per
line. Whitespace and stream fields are named `field_1`, `field_2`, and so on. Detection refuses
empty and ambiguous comma-numeric data. Use `--format` to resolve ambiguity.

