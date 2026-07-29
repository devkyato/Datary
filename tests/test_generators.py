import pytest

from datary.generators import PROFILES, generate_records


def test_all_profiles_deterministic() -> None:
    for profile in PROFILES:
        first = list(generate_records(profile, seed=7, duration=1, sample_rate=5))
        second = list(generate_records(profile, seed=7, duration=1, sample_rate=5))
        assert first == second
        assert first


def test_explicit_zero_anomaly_rates_are_honoured() -> None:
    missing = list(generate_records("missing-samples", duration=2, sample_rate=10, missing_rate=0))
    assert len(missing) == 21
    duplicated = list(
        generate_records("duplicate-samples", duration=2, sample_rate=10, duplicate_rate=0)
    )
    assert len(duplicated) == 21


def test_pid_error_matches_emitted_response() -> None:
    record = next(generate_records("pid-response", seed=7, noise=0.2))
    assert record["error"] == record["target"] - record["response"]


def test_named_anomaly_profiles_include_their_default_anomaly() -> None:
    missing = list(generate_records("missing-samples", seed=999, duration=1, sample_rate=5))
    assert len(missing) < 6
    duplicated = list(generate_records("duplicate-samples", seed=999, duration=1, sample_rate=5))
    timestamps = [record["timestamp"] for record in duplicated]
    assert len(timestamps) > len(set(timestamps))


def test_generator_rejects_nonfinite_and_unbounded_options() -> None:
    with pytest.raises(ValueError):
        list(generate_records("sine", duration=float("nan")))
    with pytest.raises(ValueError):
        list(generate_records("sine", noise=-1))
    with pytest.raises(ValueError, match="safety limit"):
        list(generate_records("sine", duration=1_000_000, sample_rate=100))
