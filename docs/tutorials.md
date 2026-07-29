# Tutorials

## Motor response

```bash
datary generate motor-speed --seed 4 --duration 10 |
  datary record motor --format jsonl --time-field timestamp --unit speed_rpm=rpm
datary inspect motor --quality --plot speed_rpm,current_a
datary report motor
```

## Network comparison

Generate and record two `network-latency` sessions with different `--noise`, then compare
`latency_ms` using `--goal lower:latency_ms`.

