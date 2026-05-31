# Raw Exports

This directory is the default root for API-backed dataset exports.

The main collector script:

```powershell
python scripts/collect_osu_ranked_dataset.py
```

creates a run directory here containing:

- `raw/sampled_users.jsonl`
- `raw/ranking_pages.jsonl`
- `raw/user_snapshots.jsonl`
- `raw/beatmaps.jsonl`
- export metadata and state checkpoints
- flattened CSV, default name: `osu_ranked_attempts_v1.csv`
- profiling summary
