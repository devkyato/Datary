# Input formats

Supported format names are `csv`, `tsv`, `json`, `jsonl`, `whitespace`, `keyvalue`, and `stream`.
An existing Datary directory is also a valid inspection, comparison, replay, or report source.

## Parsing rules

- CSV and TSV use Python's strict CSV parser, require a unique non-empty header, and support quoted
  fields containing commas, tabs, quotes, and physical newlines.
- JSON is a top-level array of objects decoded incrementally. One pending value is limited to
  16 MiB.
- JSON Lines requires one object per logical line.
- Whitespace rows receive `field_1`, `field_2`, and subsequent names.
- `key=value` uses shell-like quoting for token boundaries, but never executes tokens. Duplicate
  keys are rejected.
- `stream` reads headerless comma rows and assigns generated field names.

UTF-8 BOMs are stripped at the parser boundary. JSON duplicate keys, non-string keys, unsupported
value types, NaN, and infinity are rejected. Malformed input remains in `raw.log`; recording writes
an explanation to `invalid.jsonl`.

## Conservative scalar coercion

Delimiter-based formats use `conservative-scalars-v1`:

- an empty cell becomes a missing value;
- lowercase `true` and `false` become booleans;
- canonical integers such as `0`, `-3`, and `42` become integers;
- canonical finite decimal or exponent forms become floats;
- `00123`, `NA`, `N/A`, `none`, and other identifier-like/domain tokens remain strings.

The policy is written to the session manifest. JSON retains the types explicitly represented by
the source document.

## Detection

Detection samples at most 262,144 bytes and 20 lines. It recognizes clear JSON arrays, uniform
JSON objects, key-value rows, TSV, header-like CSV, and whitespace numeric rows. Empty input and
headerless comma-numeric input are ambiguous by design:

```bash
datary inspect numbers.txt --format stream
```

Oh! I would rather ask for one explicit flag than produce a plausible-looking parse using the
wrong schema.
