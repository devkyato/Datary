# Metric definitions

Datary keeps ordering and distribution operations separate. Observation order is used for change
metrics; a sorted view is used only for median and percentile calculations.

## General numeric metrics

For finite values \(x_1,\ldots,x_n\):

- `count`: all records considered;
- `valid_count`: finite numeric values;
- `missing_count`: records without a finite numeric value;
- `minimum`, `maximum`, `sum`, and arithmetic `mean`;
- `median` and linearly interpolated percentiles at 5, 25, 50, 75, 95, and 99%;
- sample `variance` and sample `standard_deviation` (zero for one value);
- `root_mean_square`: \(\sqrt{\sum x_i^2/n}\);
- `rate_of_change`: \(x_n-x_1\), the net ordered change per record series;
- `mean_absolute_difference`: \(\sum_{i=2}^{n}|x_i-x_{i-1}|/(n-1)\).

Missing and non-numeric values are omitted from numeric order. Integer values beyond ±2^53 are
preserved as records but excluded from binary64 analysis and receive an `invalid-values` finding;
this avoids silently rounding identifiers or counters. Their record positions remain available to
quality analysis.

## Timing metrics

Time accepts finite numeric seconds or timezone-aware ISO 8601 strings. Naive date-times are not
treated as time because their offset is ambiguous.

For positive adjacent intervals:

- mean, median, minimum, and maximum interval;
- population standard deviation as `jitter`;
- effective sample rate \(1/\text{mean interval}\);
- a gap count for intervals at least twice the median;
- global duplicate-timestamp count, including non-adjacent duplicates;
- backwards-timestamp count.

The start, end, and duration are epoch-second values when ISO 8601 input is used.

## Control-system metrics

Required roles are `time`, `target`, and `response`. Supply them with `--time-field`,
`--target-field`, and `--response-field`.

- Rise time: elapsed time between the first recorded 10% and 90% response crossings.
- Peak: maximum response for an upward step or minimum response for a downward step.
- Percentage overshoot: peak excursion beyond the final target divided by absolute step span.
- Settling time: first recorded point after the last excursion outside a ±2% band. The band uses
  the larger of absolute step span and target magnitude.
- Steady-state error: final target minus final response.
- MAE and RMSE: ordinary sample error summaries.
- IAE and ISE: trapezoidal integration over non-decreasing time intervals.

Rise, overshoot, and settling are reported only when the recorded target is stable. Crossings are
not interpolated. Warnings disclose changing targets and excluded backwards intervals.

## Network metrics

Required roles are `sequence` and `latency`; `bytes` and `time` are optional.

- Packet-loss estimate: missing integer IDs inside the observed inclusive sequence range divided
  by the expected range.
- Duplicate-packet rate: repeated valid sequence IDs divided by valid IDs.
- Out-of-order count: descending adjacent valid IDs.
- Mean, median, percentile latency, and latency jitter. Jitter is the mean absolute difference
  between consecutive valid latency observations.
- Throughput: total non-negative byte count divided by positive observed duration.

These definitions assume contiguous integer sequence identifiers and consistent latency/time
units. They are measurement summaries, not transport-protocol truth.
