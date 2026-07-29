# Reproducibility

I think of a Datary session as a small evidence bundle, not merely a convenient export.

- `raw.log` answers, “What text did the program produce?”
- `records.jsonl` answers, “What did this parser accept?”
- `invalid.jsonl` answers, “What was rejected, where, and why?”
- `manifest.json` answers, “Which Datary version, policy, roles, options, units, and commands
  describe the run?”
- metrics, quality, plots, reports, and notes keep interpretation beside the source evidence.

Session format 2 hashes the manifest and all evidentiary files. Verification also parses record
files and checks their counts. These are corruption checks, not authorship signatures. If
adversarial provenance matters, sign or version the whole session with an external trusted tool.

Synthetic records are deterministic for the same Datary version, profile, seed, and options.
Floating-point results can still vary at the last bit across Python or platform implementations;
the release verifier compares serialized generator output in separate processes on every CI
version.

Reports state their version, commands, field roles, thresholds, warnings, integrity state, and
assumptions. A reproducible calculation is still not automatically a valid experiment—the raw
input, units, collection method, and domain design remain part of the evidence.
