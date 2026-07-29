"""Tiny deterministic motor simulation for Datary examples."""
import json
import math

for index in range(101):
    timestamp = index / 20
    target = 1500.0
    speed = target * (1 - math.exp(-timestamp / 1.2))
    print(json.dumps({"timestamp": timestamp, "target_rpm": target, "speed_rpm": speed}))
