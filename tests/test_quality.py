from datary.quality import analyze_quality


def ids(records: list[dict[str, object]], time_field: str = "t") -> set[str]:
    return {item.check_id for item in analyze_quality(records, time_field)}


def test_quality_checks() -> None:
    records = [
        {"t": 0, "x": 1},
        {"t": 1, "x": 1},
        {"t": 1, "x": 1},
        {"t": 0.5, "x": 1},
        {"t": 10, "x": None},
        {"t": 11, "x": 100},
    ]
    result = ids(records)
    assert {"missing-values", "duplicate-timestamps", "timestamps-backwards", "large-timing-gaps"} <= result


def test_frozen_and_constant() -> None:
    frozen = [{"t": i, "x": 2 if i < 6 else i} for i in range(10)]
    assert "frozen-values" in ids(frozen)
    assert "constant-signal" in ids([{"t": i, "x": 2} for i in range(10)])


def test_configurable_monotonicity_and_counter_resets() -> None:
    records = [
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
