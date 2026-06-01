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
- flattened CSV, default name: `osu_country_try_data_v1.csv`
- profiling summary

To watch progress for a running collection:

```powershell
python scripts/show_collection_progress.py data/raw/<run_dir> --watch 5
```

Notes:

- progress is driven by `state.json`
- the collector seeds users from top countries, then samples country-local player ranks
- the public country player rankings endpoint currently exposes only the top `10000` users per country
- sampling is deterministic for a fixed config and `random_seed`
