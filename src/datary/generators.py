"""Deterministic synthetic data profiles."""

from __future__ import annotations

import math
import random
from typing import Any, Dict, Iterator, Optional

PROFILES = (
    "sine", "noisy-sensor", "frozen-sensor", "missing-samples", "duplicate-samples",
    "pid-response", "motor-speed", "battery-drain", "network-latency", "packet-loss",
)


def generate_records(
    profile: str,
    *,
    seed: int = 0,
    duration: float = 10.0,
    sample_rate: float = 10.0,
    noise: float = 0.05,
    missing_rate: float = 0.0,
    duplicate_rate: float = 0.0,
) -> Iterator[Dict[str, Any]]:
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}")
    if duration < 0 or sample_rate <= 0 or not 0 <= missing_rate <= 1 or not 0 <= duplicate_rate <= 1:
        raise ValueError("duration/sample-rate/rates are out of range")
    rng = random.Random(seed)
    count = int(duration * sample_rate) + 1
    previous: Optional[Dict[str, Any]] = None
    for index in range(count):
        time = index / sample_rate
        if profile in {"missing-samples", "packet-loss"} and index and rng.random() < max(missing_rate, 0.1):
            continue
        record = _profile(profile, index, time, duration, rng, noise)
        if profile == "noisy-sensor" and rng.random() < missing_rate:
            record["value"] = None
        if profile in {"duplicate-samples"} and previous and rng.random() < max(duplicate_rate, 0.1):
            yield dict(previous)
        elif previous and rng.random() < duplicate_rate:
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
        return {"timestamp": time, "target": target, "response": response + perturb, "error": target - response}
    if profile == "motor-speed":
        target = 1500.0
        speed = target * (1 - math.exp(-time / 1.5)) + perturb * 20
        return {"timestamp": time, "target_rpm": target, "speed_rpm": speed, "current_a": 2 + 8 * math.exp(-time)}
    if profile == "battery-drain":
        return {"timestamp": time, "voltage_v": 4.2 - 1.2 * time / max(duration, 1e-12) + perturb, "current_a": 0.5 + perturb / 10}
    if profile in {"network-latency", "packet-loss"}:
        return {"timestamp": time, "sequence": index, "latency_ms": max(0.0, 20 + rng.gauss(0, noise * 20)), "bytes": 1024}
    raise AssertionError(profile)
