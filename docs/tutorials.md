# Tutorials

These examples follow the same rhythm I use while working: create or run something, record it,
inspect the evidence, and only then write the report.

## Motor response

Suppose I want to see how a simulated motor approaches its target speed. I start with deterministic
data so I can repeat the exact run later:

```bash
datary generate motor-speed --seed 4 --duration 10 |
  datary record motor --format jsonl --time-field timestamp --unit speed_rpm=rpm
datary inspect motor --quality --plot speed_rpm,current_a
datary report motor
```

The pipe sends one JSON object at a time into `datary record`. Datary preserves those lines in
`raw.log`, writes accepted objects to `records.jsonl`, calculates metrics and quality findings, and
then finalizes the session. `inspect` reads that evidence back; `report` turns it into a local
Markdown narrative.

## Network comparison

Oh! Comparison is the point where I want intent to be explicit. Generate and record two
`network-latency` sessions with different `--noise`, then compare `latency_ms` using:

```bash
datary compare baseline improved --field latency_ms --goal lower:latency_ms
```

The `lower:` goal is what gives Datary permission to calculate improvement or regression. Without
it, Datary shows the measurements but does not invent a winner.

## Counter and monotonicity expectations

Some fields only make sense when I tell Datary how they should behave:

```bash
datary inspect packet-run \
  --counter-field sequence \
  --monotonic-field bytes_received \
  --quality
```

This does not change the records. It asks for two additional checks and produces explainable
findings if the selected fields decrease.
