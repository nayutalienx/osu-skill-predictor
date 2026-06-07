# Training

Project: `osu-skill-predictor`

## Purpose

This document explains how to train or refresh local model artifacts.

## Training Inputs

Current main raw dataset:

- `data/raw/osu_country_try_data_full_20260601T074107Z/osu_country_try_data_v1.csv`

Sample dataset for small local validation:

- `data/sample/osu_ranked_attempts_sample_v1.csv`

## Baseline Training Entry Point

The simplest baseline training entry point is:

```powershell
python -m ml.train
```

This:

- loads the latest raw dataset under `data/raw/`;
- cleans and engineers features;
- builds the grouped train/test split;
- trains the baseline classifier and regressor;
- writes processed outputs;
- writes canonical model artifacts into `models/`.

You can also point it to an explicit CSV:

```powershell
python -m ml.train --raw-csv data/sample/osu_ranked_attempts_sample_v1.csv
```

## Reproducibility Check

To confirm training reproducibility locally:

```powershell
python -m ml.train --raw-csv data/sample/osu_ranked_attempts_sample_v1.csv --verify-reproducibility
```

## Model Comparison Entry Point

For the fuller comparison pass:

```powershell
python -m ml.compare --evaluation-mode holdout
```

For grouped cross-validation:

```powershell
python -m ml.compare --evaluation-mode cross_validation --cv-folds 5
```

## Save Canonical Winner Models

To compare candidate models and then save the winner artifacts:

```powershell
python -m ml.compare --evaluation-mode cross_validation --cv-folds 5 --save-winners --models-root models
```

This is the recommended command for refreshing the committed canonical models.

## Training Outputs

Processed outputs go under:

- `data/processed/<raw_run_name>/`

Important processed artifacts:

- `cleaned_dataset.parquet`
- `training_dataset.parquet`
- `split_assignment.parquet`
- comparison result CSV and JSON files

Canonical model artifacts go under:

- `models/pass_model.joblib`
- `models/accuracy_model.joblib`
- `models/model_metadata.json`

## Notebook Training Options

Interactive notebooks:

- `notebooks/02_baseline_model.ipynb`
- `notebooks/03_model_comparison.ipynb`

Recommended usage:

- use `02_baseline_model.ipynb` for baseline training inspection;
- use `03_model_comparison.ipynb` to compare models and save winners.

## Practical Recommendation

For the current repo state, the most useful refresh flow is:

1. run grouped cross-validation comparison;
2. inspect the notebook plots or saved comparison CSVs;
3. save the selected winner models into `models/`.
