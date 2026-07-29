import pytest

from datary.metrics import control_metrics, network_metrics, numeric_summary, timing_metrics


def test_numeric_and_timing() -> None:
    summary = numeric_summary([1.0, 2.0, 3.0, None])
    assert summary["mean"] == 2
    assert summary["missing_count"] == 1
    timing = timing_metrics([0, 1, 2, 4, 4])
    assert timing["duplicate_timestamp_count"] == 1
    assert timing["gap_count"] == 1


def test_control_metrics() -> None:
    records = [{"t": i / 10, "target": 1.0, "response": 1 - 2.71828 ** (-i / 10)} for i in range(51)]
    result = control_metrics(records, "t", "target", "response")
    assert result["mean_absolute_error"] > 0
    assert result["rise_time"] == pytest.approx(2.2, abs=0.2)


def test_network_metrics() -> None:
    records = [
        {"seq": 1, "latency": 10, "bytes": 100},
        {"seq": 2, "latency": 20, "bytes": 100},
        {"seq": 2, "latency": 20, "bytes": 100},
        {"seq": 4, "latency": 40, "bytes": 100},
    ]
    result = network_metrics(records, "seq", "latency", "bytes")
    assert result["packet_loss_estimate"] == 0.25
    assert result["duplicate_packet_rate"] == 0.25

