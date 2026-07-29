# Metrics

General summaries use sample variance/standard deviation and linearly interpolated percentiles.
RMS is `sqrt(mean(x²))`; mean absolute difference is the mean adjacent absolute step.

Timing uses adjacent numeric timestamps: jitter is the population standard deviation of positive
intervals; effective rate is the reciprocal mean interval; gaps exceed twice the mean interval.

Control metrics require numeric time, target, and response. Rise time is 10–90% first crossing;
overshoot is `(peak-final target)/|step| × 100`; settling is the first point after which response
stays within 2% of step amplitude; error integrals use right-rectangle elapsed-time integration.

Network metrics require sequence and latency. Loss is missing IDs inside the observed inclusive
range; duplicate rate counts repeated IDs; out-of-order counts descending adjacent IDs. Latency
uses general summaries. Byte totals require a byte-count field.

