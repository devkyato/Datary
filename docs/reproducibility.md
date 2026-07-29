# Reproducibility

I think of a session as a small evidence bundle rather than a convenient export. Keep the
directory intact and the raw bytes, parsed records, invalid reasons, options, hashes, version, and
commands form an auditable chain.

The important reference points are:

- `raw.log` answers, “What did the program actually produce?”
- `records.jsonl` answers, “What did Datary accept as structured data?”
- `invalid.jsonl` answers, “What was rejected, and why?”
- `manifest.json` answers, “Which version, options, hashes, and follow-up commands describe this?”

Synthetic output is stable for the same profile, seed, and options on a compatible Datary version.
Reports include the version and assumptions so a polished summary never loses its connection to
the recorded evidence.
