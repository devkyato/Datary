import pytest

from datary.metrics import (
    control_metrics,
    network_metrics,
    numeric_summary,
    summarize_records,
    timing_metrics,
)
from datary.models import Record


def test_numeric_and_timing() -> None:
    summary = numeric_summary([1.0, 2.0, 3.0, None])
    assert summary["mean"] == 2
    assert summary["missing_count"] == 1
    timing = timing_metrics([0, 1, 2, 4, 4])
    assert timing["duplicate_timestamp_count"] == 1
    assert timing["gap_count"] == 1


def test_order_sensitive_metrics_keep_observation_order() -> None:
    summary = numeric_summary([3.0, 1.0, 2.0])
    assert summary["minimum"] == 1.0
    assert summary["median"] == 2.0
    assert summary["rate_of_change"] == -1.0
    assert summary["mean_absolute_difference"] == 1.5
    assert summary["sparkline_values"] == [3.0, 1.0, 2.0]


def test_control_metrics() -> None:
    records: list[Record] = [
        {"t": i / 10, "target": 1.0, "response": 1 - 2.71828 ** (-i / 10)} for i in range(51)
    ]
    result = control_metrics(records, "t", "target", "response")
    assert result["mean_absolute_error"] > 0
    assert result["rise_time"] == pytest.approx(2.2, abs=0.2)


def test_network_metrics() -> None:
    records: list[Record] = [
        {"seq": 1, "latency": 10, "bytes": 100},
        {"seq": 2, "latency": 20, "bytes": 100},
        {"seq": 2, "latency": 20, "bytes": 100},
        {"seq": 4, "latency": 40, "bytes": 100},
    ]
    result = network_metrics(records, "seq", "latency", "bytes")
    assert result["packet_loss_estimate"] == 0.25
    assert result["duplicate_packet_rate"] == 0.25


def test_iso8601_timing_and_network_throughput() -> None:
    records: list[Record] = [
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "seq": 1,
            "latency": 10,
            "bytes": 100,
        },
        {
            "timestamp": "2026-01-01T00:00:02Z",
            "seq": 2,
            "latency": 20,
            "bytes": 100,
        },
    ]
    timing = summarize_records(records, "timestamp")["timing"]
    assert timing["mean_interval"] == 2
    network = network_metrics(records, "seq", "latency", "bytes", "timestamp")
    assert network["throughput_bytes_per_second"] == 100


def test_non_adjacent_duplicate_timestamps_are_counted() -> None:
    assert timing_metrics([0, 1, 0])["duplicate_timestamp_count"] == 1


def test_single_timestamp_still_has_a_time_range() -> None:
    timing = timing_metrics([5])
    assert timing["start"] == timing["end"] == 5
    assert timing["duration"] == 0
    assert timing["mean_interval"] is None
