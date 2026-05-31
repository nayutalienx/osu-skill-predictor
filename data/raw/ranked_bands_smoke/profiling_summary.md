# Profiling Summary

Dataset: `osu_ranked_attempts_v1.csv`

## Collection Metadata

- Source: official osu! API v2
- Ruleset: `osu`
- Export started at: `2026-05-31T18:16:53Z`
- Export finished at: `2026-05-31T18:18:46Z`
- Export duration seconds: `113.0`
- Earliest row collected_at: `2026-05-31T18:18:38Z`
- Latest row collected_at: `2026-05-31T18:18:45Z`
- Ranking type: `performance`
- Random seed: `42`
- Band spec: `1-1000:3,1001-10000:3`
- Recent scores per user: `3`
- Best scores per user: `2`

## Size

- Rows: `18`
- Unique users: `6`
- Unique beatmaps: `17`

## Target Distribution

- Passed: `14`
- Failed: `4`
- Pass rate: `77.7778%`

## Numeric Summary

- `target_accuracy`
  - mean: `95.5837`
  - median: `97.8669`
  - min: `58.3333`
  - max: `100.0000`
- `beatmap_star_rating`
  - mean: `6.4152`
  - median: `6.4125`
  - min: `4.8420`
  - max: `8.1373`
- `beatmap_bpm`
  - mean: `187.7967`
  - median: `184.5000`
  - min: `107.5000`
  - max: `254.9200`

## Score Sources

- `best`: `12`
- `recent`: `6`

## Rows Per Ranking Band

- `1-1000`: `12`
- `1001-10000`: `6`

## Top Mods

- `NM`: `5`
- `DT`: `5`
- `HDDT`: `3`
- `HR`: `2`
- `HD`: `1`
- `HDHRDT`: `1`
- `NC`: `1`

## Observations

- This export uses deterministic band sampling, so re-running with the same config should preserve the sampled user pool.
- JSONL storage keeps raw data append-friendly and much easier to inspect than large directories of tiny JSON files.
- `best` score rows improve positive-label coverage, but source mix should be tracked during training.
- Resume safety comes from append-only user snapshots, beatmap cache reuse, and state.json checkpoints.
