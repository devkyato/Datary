# Quality checks

Every finding contains a stable check ID, severity, field, affected record or range, evidence,
threshold, explanation, assumptions, and suggested investigation. Findings are deterministic and
sorted; they are leads for review, not declarations of scientific invalidity.

## Structural and value checks

- `empty-data`
- `missing-values`
- `non-finite`
- `type-change`
- `record-shape-change`
- `record-length-change`
- `duplicate-rows`

Shape comparison uses the actual field-name set, so `{a,b}` changing to `{a,c}` is detected even
though both records have length two. Non-finite JSON input is rejected by the parser and preserved
as invalid evidence; the direct quality API also detects non-finite Python floats.

## Signal checks

- `constant-signal`
- `frozen-values`
- `sudden-spikes`
- `outliers`
- `high-noise`
- `monotonicity-violation`
- `counter-reset`

Frozen ranges retain original record positions and missing values break a run. Outliers use a
six-MAD rule; when MAD is zero, values different from the median are still surfaced. Spikes use
ten times the median absolute adjacent step, with a non-zero-step fallback when that median is
zero. High noise uses coefficient of variation and is meaningful only for ratio-scale signals.

Monotonic and counter expectations are explicit:

```bash
datary inspect session \
  --monotonic-field distance \
  --counter-field packet_count \
  --quality
```

## Timing and sequence checks

- `duplicate-timestamps`, including duplicates that are not adjacent;
- `timestamps-backwards`;
- `irregular-timing`, outside ±20% of the median positive interval;
- `large-timing-gaps`, over twice the median positive interval;
- `packet-loss`, when a sequence field role is supplied.

Domain thresholds vary. Treat the raw records, units, system limits, and experimental design as
the final authority.
