# Sample Starter Dataset

Files in this folder are tracked starter artifacts for local development.

## Purpose

`osu_ranked_attempts_sample_v1.csv` exists so the project can:

- load a schema-compatible dataset locally without external services;
- exercise feature engineering and training code before live export is wired in;
- validate the API request and prediction contract against realistic column names.

## Provenance

This CSV is a small hand-authored bootstrap dataset.

- It follows the schema in `docs/dataset_schema.md`.
- It includes both MVP targets: `target_passed` and `target_accuracy`.
- It is intended for local development only.

For a real API-backed export, use:

```powershell
python scripts/collect_osu_ranked_dataset.py
```

That collector requires:

- `OSU_CLIENT_ID`
- `OSU_CLIENT_SECRET`

and writes resumable raw snapshots plus a flattened CSV under `data/raw/`.

The current live collector uses country-seeded sampling:

- select top countries from the osu! country rankings endpoint
- sample players from each country's top local leaderboard window
- collect recent and best attempts for those sampled players
