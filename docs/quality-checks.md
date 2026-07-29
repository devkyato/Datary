# Quality checks

Findings are deterministic objects containing ID, severity, field, affected range, evidence,
threshold, explanation, assumptions, and investigation advice. Rules cover missing/non-finite
values, duplicate rows/timestamps, backward time, irregularity/gaps, record shape/type changes,
constant/frozen signals, robust spikes/outliers, high relative noise, and sequence gaps.
Thresholds are heuristics and must be reviewed against domain knowledge.

Use repeatable inspection options for domain expectations:

```bash
datary inspect session --monotonic-field distance --counter-field packet_count --quality
```

`monotonicity-violation` reports decreases in explicitly non-decreasing fields.
`counter-reset` reports decreases in fields explicitly identified as counters. Missing values are
ignored between consecutive valid values; findings document that assumption and recommend checking
record ordering, restarts, rollover, and counter width.
