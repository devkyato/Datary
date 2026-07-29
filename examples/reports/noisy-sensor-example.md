# Datary report: noisy-sensor-example

- Datary version: `0.1.0`
- Started: `2026-07-29T13:43:20.211495+08:00`
- Ended: `2026-07-29T13:43:20.221953+08:00`
- Input format: `jsonl`
- Records: 21 valid, 0 invalid

## Reproduction

- compare: `datary compare noisy-sensor-example OTHER`
- inspect: `datary inspect noisy-sensor-example`
- replay: `datary replay noisy-sensor-example`
- report: `datary report noisy-sensor-example`

## Data schema

| Field | Type | Unit |
|---|---|---|
| timestamp | number |  |
| value | number |  |

## Descriptive statistics

### timestamp

- Mean: 1.0
- Median: 1.0
- Range: 0.0 to 2.0

### value

- Mean: 20.700166470541177
- Median: 20.80704917255715
- Range: 20.064409237657774 to 21.03591726892986

## Quality findings

- **high-noise** (info): Variation is high relative to the mean. Field: `timestamp`; affected: all.

## Input hashes

- `data.csv`: `3943c5fe0029450dc7adbd01ce800f1839760a4df9cc6a8c370bdb4c68a7c187`
- `metrics.json`: `ae371e6a73b6fec4e2c4c538df7845c9c5e731851d5560d009c607e65881563d`
- `quality.json`: `b86c70595fbbafb7b8180847ea53cf369fa14d69d3cc56e2e0c520e419e3e94f`
- `raw.log`: `8f453644d5e733e000bac97a81a7db5e66f158aa67f694499ec91509ac021760`
- `records.jsonl`: `8f453644d5e733e000bac97a81a7db5e66f158aa67f694499ec91509ac021760`

## Warnings and assumptions

- Statistics describe recorded data; they do not establish scientific validity.
- Quality checks are heuristics and require domain review.

## Plots

Plots are stored in the session `plots/` directory.
