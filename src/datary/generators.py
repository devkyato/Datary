"""Deterministic synthetic data profiles."""

from __future__ import annotations

import math
import random
from typing import Any, Dict, Iterator, Optional

PROFILES = (
    "sine",
    "noisy-sensor",
    "frozen-sensor",
    "missing-samples",
    "duplicate-samples",
    "pid-response",
    "motor-speed",
    "battery-drain",
    "network-latency",
    "packet-loss",
)
MAX_GENERATED_RECORDS = 10_000_000


def generate_records(
    profile: str,
    *,
    seed: int = 0,
    duration: float = 10.0,
    sample_rate: float = 10.0,
    noise: float = 0.05,
    missing_rate: Optional[float] = None,
    duplicate_rate: Optional[float] = None,
) -> Iterator[Dict[str, Any]]:
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}")
    if (
        not math.isfinite(duration)
        or not math.isfinite(sample_rate)
        or not math.isfinite(noise)
        or duration < 0
        or sample_rate <= 0
        or noise < 0
        or (missing_rate is not None and not 0 <= missing_rate <= 1)
        or (duplicate_rate is not None and not 0 <= duplicate_rate <= 1)
        or (missing_rate is not None and not math.isfinite(missing_rate))
        or (duplicate_rate is not None and not math.isfinite(duplicate_rate))
    ):
        raise ValueError("duration/sample-rate/rates are out of range")
    default_missing = missing_rate is None and profile in {"missing-samples", "packet-loss"}
    default_duplicate = duplicate_rate is None and profile == "duplicate-samples"
    effective_missing = 0.1 if default_missing else (missing_rate or 0.0)
    effective_duplicate = 0.1 if default_duplicate else (duplicate_rate or 0.0)
    rng = random.Random(seed)
    requested_count = duration * sample_rate
    if not math.isfinite(requested_count) or requested_count + 1 > MAX_GENERATED_RECORDS:
        raise ValueError(
            f"generated dataset exceeds safety limit ({MAX_GENERATED_RECORDS} records)"
        )
    count = int(requested_count) + 1
    previous: Optional[Dict[str, Any]] = None
    for index in range(count):
        time = index / sample_rate
        if (
            profile in {"missing-samples", "packet-loss"}
            and index
            and effective_missing > 0
            and (
                (default_missing and index == max(1, count // 2))
                or rng.random() < effective_missing
            )
        ):
            continue
        record = _profile(profile, index, time, duration, rng, noise)
        if profile == "noisy-sensor" and effective_missing > 0 and rng.random() < effective_missing:
            record["value"] = None
        if previous:
            if profile == "duplicate-samples":
                if (
                    default_duplicate and index == max(1, count // 2)
                ) or rng.random() < effective_duplicate:
                    yield dict(previous)
            elif effective_duplicate > 0 and rng.random() < effective_duplicate:
                yield dict(previous)
        yield record
        previous = record


def _profile(
    profile: str, index: int, time: float, duration: float, rng: random.Random, noise: float
) -> Dict[str, Any]:
    perturb = rng.gauss(0, noise)
    if profile == "sine":
        return {"timestamp": time, "value": math.sin(2 * math.pi * time) + perturb}
    if profile in {"noisy-sensor", "missing-samples", "duplicate-samples"}:
        return {"timestamp": time, "value": 20 + math.sin(time) + perturb}
    if profile == "frozen-sensor":
        value = 20.0 if duration * 0.35 <= time <= duration * 0.7 else 20 + math.sin(time) + perturb
        return {"timestamp": time, "value": value}
    if profile == "pid-response":
        target = 1.0
        response = 1 - math.exp(-time) * (math.cos(2 * time) + 0.2 * math.sin(2 * time))
        measured_response = response + perturb
        return {
            "timestamp": time,
            "target": target,
            "response": measured_response,
            "error": target - measured_response,
        }
    if profile == "motor-speed":
        target = 1500.0
        speed = target * (1 - math.exp(-time / 1.5)) + perturb * 20
        return {
            "timestamp": time,
            "target_rpm": target,
            "speed_rpm": speed,
            "current_a": 2 + 8 * math.exp(-time),
        }
    if profile == "battery-drain":
        return {
            "timestamp": time,
            "voltage_v": 4.2 - 1.2 * time / max(duration, 1e-12) + perturb,
            "current_a": 0.5 + perturb / 10,
        }
    if profile in {"network-latency", "packet-loss"}:
        return {
            "timestamp": time,
            "sequence": index,
            "latency_ms": max(0.0, 20 + rng.gauss(0, noise * 20)),
            "bytes": 1024,
        }
    raise AssertionError(profile)
