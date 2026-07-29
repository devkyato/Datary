from datary.generators import PROFILES, generate_records


def test_all_profiles_deterministic() -> None:
    for profile in PROFILES:
        first = list(generate_records(profile, seed=7, duration=1, sample_rate=5))
        second = list(generate_records(profile, seed=7, duration=1, sample_rate=5))
        assert first == second
        assert first

