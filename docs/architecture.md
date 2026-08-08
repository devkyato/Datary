# Architecture

I wanted Datary's architecture to follow the way I explain a run: capture first, interpret second,
and publish only after every critical artifact is ready.

```text
stdin/file
   |
   +--> raw.log
   |
parser --> records.jsonl / invalid.jsonl
   |
temporary disk-backed analysis
   |
metrics + quality + data.csv + manifest + hashes
   |
atomic session publication
```

## Boundaries

- `formats.py` detects only clear input signatures.
- `parsers.py` turns inert text into JSON-compatible records.
- `recorder.py` owns staging, flush/fsync, interruption, overwrite recovery, and publication.
- `analysis_store.py` uses temporary local SQLite for exact bounded-memory distribution and
  quality calculations. It is not a catalogue or session dependency.
- `sessions.py` validates manifests, rejects symlinked trust boundaries, reads records, and
  verifies integrity.
- `metrics.py` and `quality.py` provide the direct in-memory analytical API.
- `comparison.py`, `replay.py`, `plotting.py`, `reports.py`, and `conversion.py` consume those
  boundaries without executing data.
- `cli.py` is orchestration and terminal rendering, not analytical logic.

The temporary database grows with input on disk, while resident analysis state is bounded by
field count and small batches. Exact percentiles use indexed disk ordering rather than retaining
every measurement in a Python list.

The recorder regression feeds 50,000 generated records without first storing the source and
enforces a 32 MiB Python-heap ceiling. That catches accidental record-list accumulation; it is not
an operating-system RSS guarantee or a substitute for deployment-specific disk sizing.

Oh! SQLite here is deliberately disposable. Published sessions remain ordinary portable files;
there is no daemon, account, central database, network layer, or hidden migration service.

## Failure model

New recordings are built beside the target. An overwrite renames the old directory to a private
backup only after the replacement is complete, then atomically renames the replacement into place.
If publication fails, the backup is restored. Critical streams flush and `fsync` before analysis.
Critical JSON and text outputs use same-directory temporary files and atomic replacement.

Core operation uses only the standard library. Matplotlib is imported lazily after forcing `Agg`.
Plot generation may downsample series for display; downsample parameters are written beside the
image and never rewrite published records.
