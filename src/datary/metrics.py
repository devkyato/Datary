"""General, timing, control-system, and network metrics."""

from __future__ import annotations

import math
import statistics
from typing import Any, Dict, Optional, Sequence

from datary.models import Record
from datary.utils import finite_number


def numeric_summary(values: Sequence[Optional[float]]) -> Dict[str, Any]:
    clean = sorted(value for value in values if value is not None and math.isfinite(value))
    missing = len(values) - len(clean)
    if not clean:
        return {"count": len(values), "valid_count": 0, "missing_count": missing}
    differences = [abs(b - a) for a, b in zip(clean, clean[1:])]
    return {
        "count": len(values),
        "valid_count": len(clean),
        "missing_count": missing,
        "minimum": clean[0],
        "maximum": clean[-1],
        "mean": statistics.fmean(clean),
        "median": statistics.median(clean),
        "standard_deviation": statistics.stdev(clean) if len(clean) > 1 else 0.0,
        "variance": statistics.variance(clean) if len(clean) > 1 else 0.0,
        "percentiles": {str(p): _percentile(clean, p) for p in (5, 25, 50, 75, 95, 99)},
        "sum": math.fsum(clean),
        "rate_of_change": clean[-1] - clean[0] if len(clean) > 1 else 0.0,
        "root_mean_square": math.sqrt(statistics.fmean([value * value for value in clean])),
        "mean_absolute_difference": statistics.fmean(differences) if differences else 0.0,
    }


def timing_metrics(times: Sequence[float]) -> Dict[str, Any]:
    intervals = [b - a for a, b in zip(times, times[1:])]
    positive = [value for value in intervals if value > 0]
    if not intervals:
        return {}
    mean = statistics.fmean(positive) if positive else 0.0
    return {
        "mean_interval": mean,
        "median_interval": statistics.median(positive) if positive else 0.0,
        "minimum_interval": min(intervals),
        "maximum_interval": max(intervals),
        "jitter": statistics.pstdev(positive) if len(positive) > 1 else 0.0,
        "effective_sample_rate": 1.0 / mean if mean > 0 else None,
        "gap_count": sum(
            1
            for value in positive
            if statistics.median(positive) > 0
            and value >= statistics.median(positive) * 2
        ),
        "duplicate_timestamp_count": sum(1 for value in intervals if value == 0),
        "backward_timestamp_count": sum(1 for value in intervals if value < 0),
    }


def summarize_records(records: Sequence[Record], time_field: Optional[str] = None) -> Dict[str, Any]:
    fields = sorted({key for record in records for key in record})
    summaries: Dict[str, Any] = {}
    for field in fields:
        values = [finite_number(record.get(field)) for record in records]
        if any(value is not None for value in values):
            summaries[field] = numeric_summary(values)
    times = [finite_number(record.get(time_field)) for record in records] if time_field else []
    return {
        "numeric": summaries,
        "timing": timing_metrics([value for value in times if value is not None]),
    }


def control_metrics(
    records: Sequence[Record], time_field: str, target_field: str, response_field: str
) -> Dict[str, Any]:
    points = [
        (finite_number(r.get(time_field)), finite_number(r.get(target_field)), finite_number(r.get(response_field)))
        for r in records
    ]
    clean = [(t, target, response) for t, target, response in points if None not in (t, target, response)]
    if len(clean) < 2:
        return {}
    times = [item[0] for item in clean if item[0] is not None]
    targets = [item[1] for item in clean if item[1] is not None]
    responses = [item[2] for item in clean if item[2] is not None]
    final_target = targets[-1]
    initial = responses[0]
    span = final_target - initial
    errors = [target - response for target, response in zip(targets, responses)]
    rise_start = _first_crossing(times, responses, initial + span * 0.1, span)
    rise_end = _first_crossing(times, responses, initial + span * 0.9, span)
    peak = max(responses) if span >= 0 else min(responses)
    overshoot = ((peak - final_target) / abs(span) * 100) if span else 0.0
    tolerance = abs(span) * 0.02
    settling = None
    for index in range(len(responses)):
        if all(abs(value - final_target) <= tolerance for value in responses[index:]):
            settling = times[index] - times[0]
            break
    dt_errors = [
        (times[i] - times[i - 1], errors[i]) for i in range(1, len(times)) if times[i] >= times[i - 1]
    ]
    return {
        "rise_time": rise_end - rise_start if rise_start is not None and rise_end is not None else None,
        "peak_value": peak,
        "percentage_overshoot": overshoot,
        "settling_time": settling,
        "steady_state_error": errors[-1],
        "mean_absolute_error": statistics.fmean(abs(value) for value in errors),
        "root_mean_squared_error": math.sqrt(statistics.fmean(value * value for value in errors)),
        "integral_absolute_error": math.fsum(dt * abs(error) for dt, error in dt_errors),
        "integral_squared_error": math.fsum(dt * error * error for dt, error in dt_errors),
    }


def network_metrics(
    records: Sequence[Record], sequence_field: str, latency_field: str, bytes_field: Optional[str] = None
) -> Dict[str, Any]:
    sequences = [finite_number(record.get(sequence_field)) for record in records]
    valid_sequences = [int(value) for value in sequences if value is not None]
    latencies = [finite_number(record.get(latency_field)) for record in records]
    unique = set(valid_sequences)
    expected = max(unique) - min(unique) + 1 if unique else 0
    duplicates = len(valid_sequences) - len(unique)
    result = {
        "packet_loss_estimate": (expected - len(unique)) / expected if expected else None,
        "duplicate_packet_rate": duplicates / len(valid_sequences) if valid_sequences else None,
        "out_of_order_count": sum(1 for a, b in zip(valid_sequences, valid_sequences[1:]) if b < a),
        "latency": numeric_summary(latencies),
    }
    if bytes_field:
        byte_values = [finite_number(record.get(bytes_field)) for record in records]
        result["total_bytes"] = math.fsum(value for value in byte_values if value is not None)
    return result


def _percentile(values: Sequence[float], percentile: int) -> float:
    if len(values) == 1:
        return values[0]
    index = (len(values) - 1) * percentile / 100
    low, high = math.floor(index), math.ceil(index)
    return values[low] if low == high else values[low] * (high - index) + values[high] * (index - low)


def _first_crossing(times: Sequence[float], values: Sequence[float], level: float, direction: float) -> Optional[float]:
    for time, value in zip(times, values):
        if (value >= level) if direction >= 0 else (value <= level):
            return time
    return None
