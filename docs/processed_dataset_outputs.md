# Processed Dataset Outputs

Project: `osu-skill-predictor`

## Purpose

This document defines which processed datasets should be saved under `data/processed/` for V1.

The goal is to keep the pipeline simple while still saving enough intermediate artifacts to:

- avoid re-running raw cleaning every time;
- make train/test splitting reproducible;
- support later model training and debugging.

## V1 Design Principles

For the first iteration:

- save a small number of clearly named artifacts
- prefer one canonical binary table format for large processed data
- separate "cleaned row table" from "feature-ready training table"
- save split membership explicitly so future runs reuse the same partition

## Chosen Save Format

Primary format:

- Parquet

Reason:

- smaller than CSV for large tables
- preserves numeric types better than CSV
- faster to load for repeated local training
- easy to use with pandas and common Python ML tooling

Secondary inspection format:

- no mandatory CSV copy for processed artifacts in V1

Reason:

- the raw export already includes a CSV
- duplicating every processed artifact in CSV adds storage noise
- CSV can be produced ad hoc later for debugging if needed

Metadata format:

- JSON

Reason:

- good for split manifests, row counts, column lists, seeds, and provenance notes

## Planned `data/processed/` Layout

V1 should save artifacts under a run-scoped processed directory, for example:

```text
data/processed/<run_name>/
```

Recommended example:

```text
data/processed/osu_country_try_data_v1_20260602/
```

Inside that directory, save these files:

- `cleaned_dataset.parquet`
- `training_dataset.parquet`
- `split_assignment.parquet`
- `dataset_metadata.json`

## Saved Artifacts

### `cleaned_dataset.parquet`

Purpose:

- canonical post-validation dataset
- output after raw loading, required-column enforcement, missing-value handling, basic deduplication, and type normalization

What it should contain:

- one row per retained score event
- all required core columns
- optional columns that survived cleaning
- no model-only engineered helper columns unless they are part of the canonical cleaned table

Typical transformations already applied:

- invalid rows dropped according to `docs/missing_value_policy.md`
- `mods_raw` defaulted to empty string if needed
- dtypes normalized
- duplicate rows removed

Why save it:

- this is the stable starting point for any later feature engineering
- lets the team inspect exactly which rows survived raw-data validation

### `training_dataset.parquet`

Purpose:

- feature-ready dataset for model training

What it should contain:

- rows from `cleaned_dataset.parquet`
- selected engineered features for the first baseline
- target columns kept alongside features
- columns needed for grouping or diagnostics, such as `user_id`, `beatmap_id`, and `score_source`

Typical transformations already applied:

- helper feature creation such as parsed mod flags or simple buckets
- optional feature filtering
- column selection for the baseline training set

What it should not contain:

- fitted scaler outputs that depend on train-only statistics across the whole dataset
- train/test-imputed values produced before splitting

Reason:

- preprocessing that learns from data must still be fit on the training split only
- the saved training dataset should be feature-ready, not leakage-ready

### `split_assignment.parquet`

Purpose:

- explicit record of train/test membership for each retained row

What it should contain:

- `row_id`
- `user_id`
- split label such as `train` or `test`
- split seed
- split version or strategy name

Recommended columns:

- `row_id`
- `user_id`
- `split_name`
- `split_random_seed`
- `split_strategy`

Recommended values:

- `split_name`: `train`, `test`
- `split_strategy`: `grouped_user_shuffle_v1`
- `split_random_seed`: `42`

Why save it:

- guarantees the same split can be reused across notebooks and scripts
- prevents accidental re-splitting with drift
- makes experiment comparisons fair

### `dataset_metadata.json`

Purpose:

- compact metadata about the processed run

What it should contain:

- source raw run path
- processed timestamp
- row counts before and after cleaning
- unique user count
- unique beatmap count
- list of saved files
- split strategy summary
- split seed
- selected target columns
- selected feature columns

Why save it:

- gives one place to inspect what this processed run actually represents
- makes later debugging and model-card writing easier

## Artifact Purposes Summary

| Artifact | Format | Purpose |
|---|---|---|
| `cleaned_dataset.parquet` | Parquet | Validated, deduplicated, type-normalized row table |
| `training_dataset.parquet` | Parquet | Feature-ready dataset for baseline model work |
| `split_assignment.parquet` | Parquet | Reproducible train/test membership by row |
| `dataset_metadata.json` | JSON | Provenance, counts, split config, and column summary |

## What Should Not Be Saved in V1

Do not save these as mandatory processed outputs yet:

- separate NumPy arrays like `X_train.npy` or `y_train.npy`
- fully transformed one-hot encoded matrices
- scaler-normalized full-dataset outputs
- model-specific intermediate files for every experiment
- duplicate CSV copies of every processed artifact

Reason:

- these artifacts are too estimator-specific
- they increase storage noise
- they are more appropriate once the training pipeline is stable

## Relationship Between Raw and Processed Data

Expected flow:

1. raw collector run under `data/raw/<raw_run>/`
2. cleaned validated table saved to `data/processed/<processed_run>/cleaned_dataset.parquet`
3. feature-ready table saved to `data/processed/<processed_run>/training_dataset.parquet`
4. split membership saved to `data/processed/<processed_run>/split_assignment.parquet`

This keeps raw extraction, cleaning, and modeling preparation separate.

## Naming Recommendation

Use run-scoped processed directories rather than overwriting one global file.

Recommended naming pattern:

- directory: `data/processed/<dataset_name>_<YYYYMMDD>/`
- files inside: fixed canonical names

Example:

```text
data/processed/osu_country_try_data_v1_20260602/
  cleaned_dataset.parquet
  training_dataset.parquet
  split_assignment.parquet
  dataset_metadata.json
```

This is simpler than encoding every detail into filenames.

## V1 Practical Recommendation

For the first processed-data implementation:

- create one processed run directory per raw input run
- save `cleaned_dataset.parquet`
- save `training_dataset.parquet`
- save `split_assignment.parquet`
- save `dataset_metadata.json`
- use Parquet for tables and JSON for metadata

This is enough structure for later training work without over-designing the pipeline.
