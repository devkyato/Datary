from datary.models import Record
from datary.quality import analyze_quality


def ids(records: list[Record], time_field: str = "t") -> set[str]:
    return {item.check_id for item in analyze_quality(records, time_field)}


def test_quality_checks() -> None:
    records: list[Record] = [
        {"t": 0, "x": 1},
        {"t": 1, "x": 1},
        {"t": 1, "x": 1},
        {"t": 0.5, "x": 1},
        {"t": 10, "x": None},
        {"t": 11, "x": 100},
    ]
    result = ids(records)
    assert {
        "missing-values",
        "duplicate-timestamps",
        "timestamps-backwards",
        "large-timing-gaps",
    } <= result


def test_frozen_and_constant() -> None:
    frozen: list[Record] = [{"t": i, "x": 2 if i < 6 else i} for i in range(10)]
    assert "frozen-values" in ids(frozen)
    constant: list[Record] = [{"t": i, "x": 2} for i in range(10)]
    assert "constant-signal" in ids(constant)


def test_quality_preserves_original_indices_and_detects_schema_changes() -> None:
    records: list[Record] = [
        {"a": 1, "x": 0},
        {"a": 2, "x": None},
        {"b": 3, "x": 2},
        {"b": 4, "x": 2},
        {"b": 5, "x": 2},
        {"b": 6, "x": 2},
        {"b": 7, "x": 2},
        {"b": 8, "x": 3},
    ]
    findings = analyze_quality(records)
    by_id = {finding.check_id: finding for finding in findings}
    assert by_id["frozen-values"].affected == "2-6"
    assert "record-shape-change" in by_id


def test_zero_mad_still_finds_isolated_anomaly() -> None:
    records: list[Record] = [{"x": value} for value in [0, 0, 0, 0, 100, 0]]
    findings = analyze_quality(records)
    assert {"outliers", "sudden-spikes"} <= {finding.check_id for finding in findings}


def test_non_adjacent_duplicate_timestamp_is_reported() -> None:
    records: list[Record] = [{"t": 0}, {"t": 1}, {"t": 0}]
    findings = analyze_quality(records, "t")
    duplicate = next(finding for finding in findings if finding.check_id == "duplicate-timestamps")
    assert duplicate.affected == "2"


def test_time_field_is_not_misclassified_as_a_noisy_signal() -> None:
    records: list[Record] = [{"t": index} for index in range(20)]
    findings = analyze_quality(records, "t")
    assert not any(
        finding.check_id == "high-noise" and finding.field == "t" for finding in findings
    )


def test_configurable_monotonicity_and_counter_resets() -> None:
    records: list[Record] = [
        {"distance": 0, "packets": 10},
        {"distance": 2, "packets": 11},
        {"distance": 1, "packets": 1},
    ]
    findings = analyze_quality(
        records,
        monotonic_fields=["distance"],
        counter_fields=["packets"],
    )
    by_id = {finding.check_id: finding for finding in findings}
    assert by_id["monotonicity-violation"].field == "distance"
    assert by_id["monotonicity-violation"].affected == "2"
    assert by_id["counter-reset"].field == "packets"
    assert by_id["counter-reset"].evidence == 1
