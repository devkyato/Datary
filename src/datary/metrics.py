"""General, timing, control-system, and network metrics."""

from __future__ import annotations

import math
import statistics
from typing import Any, Dict, Optional, Sequence

from datary.models import Record
from datary.utils import finite_number, temporal_number


def numeric_summary(values: Sequence[Optional[float]]) -> Dict[str, Any]:
    ordered = [value for value in values if value is not None and math.isfinite(value)]
    sorted_values = sorted(ordered)
    missing = len(values) - len(ordered)
    if not ordered:
        return {"count": len(values), "valid_count": 0, "missing_count": missing}
    differences = [abs(b - a) for a, b in zip(ordered, ordered[1:])]
    return {
        "count": len(values),
        "valid_count": len(ordered),
        "missing_count": missing,
        "minimum": sorted_values[0],
        "maximum": sorted_values[-1],
        "mean": statistics.fmean(ordered),
        "median": statistics.median(sorted_values),
        "standard_deviation": statistics.stdev(ordered) if len(ordered) > 1 else 0.0,
        "variance": statistics.variance(ordered) if len(ordered) > 1 else 0.0,
        "percentiles": {str(p): _percentile(sorted_values, p) for p in (5, 25, 50, 75, 95, 99)},
        "sum": math.fsum(ordered),
        "rate_of_change": ordered[-1] - ordered[0] if len(ordered) > 1 else 0.0,
        "mean_absolute_difference": statistics.fmean(differences) if differences else 0.0,
        "root_mean_square": math.sqrt(statistics.fmean([value * value for value in ordered])),
        "sparkline_values": _downsample(ordered, 40),
    }


def timing_metrics(times: Sequence[float]) -> Dict[str, Any]:
    if not times:
        return {}
    intervals = [b - a for a, b in zip(times, times[1:])]
    positive = [value for value in intervals if value > 0]
    if not intervals:
        return {
            "start": times[0],
            "end": times[0],
            "duration": 0.0,
            "mean_interval": None,
            "median_interval": None,
            "minimum_interval": None,
            "maximum_interval": None,
            "jitter": 0.0,
            "effective_sample_rate": None,
            "gap_count": 0,
            "duplicate_timestamp_count": 0,
            "backward_timestamp_count": 0,
        }
    mean = statistics.fmean(positive) if positive else 0.0
    median = statistics.median(positive) if positive else 0.0
    return {
        "start": times[0],
        "end": times[-1],
        "duration": times[-1] - times[0],
        "mean_interval": mean,
        "median_interval": median,
        "minimum_interval": min(intervals),
        "maximum_interval": max(intervals),
        "jitter": statistics.pstdev(positive) if len(positive) > 1 else 0.0,
        "effective_sample_rate": 1.0 / mean if mean > 0 else None,
        "gap_count": sum(1 for value in positive if median > 0 and value >= median * 2),
        "duplicate_timestamp_count": len(times) - len(set(times)),
        "backward_timestamp_count": sum(1 for value in intervals if value < 0),
    }


def summarize_records(
    records: Sequence[Record], time_field: Optional[str] = None
) -> Dict[str, Any]:
    fields = sorted({key for record in records for key in record})
    summaries: Dict[str, Any] = {}
    for field in fields:
        values = [finite_number(record.get(field)) for record in records]
        if any(value is not None for value in values):
            summaries[field] = numeric_summary(values)
    times = [temporal_number(record.get(time_field)) for record in records] if time_field else []
    return {
        "numeric": summaries,
        "timing": timing_metrics([value for value in times if value is not None]),
    }


def control_metrics(
    records: Sequence[Record], time_field: str, target_field: str, response_field: str
) -> Dict[str, Any]:
    points = [
        (
            temporal_number(r.get(time_field)),
            finite_number(r.get(target_field)),
            finite_number(r.get(response_field)),
        )
        for r in records
    ]
    clean = [
        (t, target, response) for t, target, response in points if None not in (t, target, response)
    ]
    if len(clean) < 2:
        return {}
    times = [item[0] for item in clean if item[0] is not None]
    targets = [item[1] for item in clean if item[1] is not None]
    responses = [item[2] for item in clean if item[2] is not None]
    final_target = targets[-1]
    initial = responses[0]
    span = final_target - initial
    errors = [target - response for target, response in zip(targets, responses)]
    target_span = max(targets) - min(targets)
    stable_target = target_span <= max(abs(final_target), 1.0) * 1e-9
    rise_start = (
        _first_crossing(times, responses, initial + span * 0.1, span) if stable_target else None
    )
    rise_end = (
        _first_crossing(times, responses, initial + span * 0.9, span) if stable_target else None
    )
    peak = max(responses) if span >= 0 else min(responses)
    overshoot = (
        (
            (peak - final_target) / abs(span) * 100
            if span >= 0
            else (final_target - peak) / abs(span) * 100
        )
        if span and stable_target
        else None
    )
    tolerance = max(abs(span), abs(final_target), 1e-12) * 0.02
    settling: Optional[float] = None
    if stable_target:
        for index in range(len(responses)):
            if all(abs(value - final_target) <= tolerance for value in responses[index:]):
                settling = times[index] - times[0]
                break
    dt_errors = [
        (
            times[i] - times[i - 1],
            errors[i - 1],
            errors[i],
        )
        for i in range(1, len(times))
        if times[i] >= times[i - 1]
    ]
    return {
        "rise_time": rise_end - rise_start
        if rise_start is not None and rise_end is not None
        else None,
        "peak_value": peak,
        "percentage_overshoot": overshoot,
        "settling_time": settling,
        "steady_state_error": errors[-1],
        "mean_absolute_error": statistics.fmean(abs(value) for value in errors),
        "root_mean_squared_error": math.sqrt(statistics.fmean(value * value for value in errors)),
        "integral_absolute_error": math.fsum(
            dt * (abs(previous) + abs(current)) / 2 for dt, previous, current in dt_errors
        ),
        "integral_squared_error": math.fsum(
            dt * (previous * previous + current * current) / 2
            for dt, previous, current in dt_errors
        ),
        "assumptions": [
            "Rise time, overshoot, and settling time require a stable step target.",
            "Rise-time crossings use recorded samples without interpolation.",
            "Settling uses a ±2% band based on the larger of step span or target magnitude.",
            "Error integrals use trapezoidal integration over non-decreasing timestamps.",
        ],
        "warnings": (
            []
            if stable_target
            else ["The target changes during the record; step-response metrics are not reported."]
        ),
    }


def network_metrics(
    records: Sequence[Record],
    sequence_field: str,
    latency_field: str,
    bytes_field: Optional[str] = None,
    time_field: Optional[str] = None,
) -> Dict[str, Any]:
    sequences = [finite_number(record.get(sequence_field)) for record in records]
    valid_sequences = [
        int(value) for value in sequences if value is not None and float(value).is_integer()
    ]
    invalid_sequence_count = sum(
        1 for value in sequences if value is not None and not float(value).is_integer()
    )
    raw_latencies = [finite_number(record.get(latency_field)) for record in records]
    negative_latency_count = sum(1 for value in raw_latencies if value is not None and value < 0)
    latencies = [value if value is None or value >= 0 else None for value in raw_latencies]
    unique = set(valid_sequences)
    expected = max(unique) - min(unique) + 1 if unique else 0
    duplicates = len(valid_sequences) - len(unique)
    latency_summary = numeric_summary(latencies)
    result: Dict[str, Any] = {
        "packet_loss_estimate": (expected - len(unique)) / expected if expected else None,
        "duplicate_packet_rate": duplicates / len(valid_sequences) if valid_sequences else None,
        "out_of_order_count": sum(1 for a, b in zip(valid_sequences, valid_sequences[1:]) if b < a),
        "latency": latency_summary,
        "mean_latency": latency_summary.get("mean"),
        "median_latency": latency_summary.get("median"),
        "latency_jitter": latency_summary.get("mean_absolute_difference"),
        "percentile_latency": latency_summary.get("percentiles", {}),
        "assumptions": [
            "Sequence identifiers are expected to be contiguous integers.",
            "Latency jitter is the mean absolute difference between consecutive valid samples.",
        ],
        "warnings": [
            warning
            for warning in (
                (
                    f"{invalid_sequence_count} non-integer sequence value(s) were excluded."
                    if invalid_sequence_count
                    else ""
                ),
                (
                    f"{negative_latency_count} negative latency value(s) were excluded."
                    if negative_latency_count
                    else ""
                ),
            )
            if warning
        ],
    }
    if bytes_field:
        raw_bytes = [finite_number(record.get(bytes_field)) for record in records]
        negative_bytes = sum(1 for value in raw_bytes if value is not None and value < 0)
        total_bytes = math.fsum(value for value in raw_bytes if value is not None and value >= 0)
        if negative_bytes:
            result["warnings"].append(f"{negative_bytes} negative byte count(s) were excluded.")
        result["total_bytes"] = total_bytes
        selected_time = time_field
        if selected_time is None:
            selected_time = next(
                (
                    candidate
                    for candidate in ("timestamp", "time", "t")
                    if any(candidate in record for record in records)
                ),
                None,
            )
        times = (
            [temporal_number(record.get(selected_time)) for record in records]
            if selected_time
            else []
        )
        valid_times = [value for value in times if value is not None]
        duration = valid_times[-1] - valid_times[0] if len(valid_times) > 1 else 0.0
        result["throughput_bytes_per_second"] = total_bytes / duration if duration > 0 else None
    return result


def _percentile(values: Sequence[float], percentile: int) -> float:
    if len(values) == 1:
        return values[0]
    index = (len(values) - 1) * percentile / 100
    low, high = math.floor(index), math.ceil(index)
    return (
        values[low] if low == high else values[low] * (high - index) + values[high] * (index - low)
    )


def _downsample(values: Sequence[float], maximum: int) -> list[float]:
    if len(values) <= maximum:
        return list(values)
    return [values[round(index * (len(values) - 1) / (maximum - 1))] for index in range(maximum)]


def _first_crossing(
    times: Sequence[float], values: Sequence[float], level: float, direction: float
) -> Optional[float]:
    for time, value in zip(times, values):
        if (value >= level) if direction >= 0 else (value <= level):
            return time
    return None
