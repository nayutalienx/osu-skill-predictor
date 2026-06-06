# Serialized Artifact Outputs

Project: `osu-skill-predictor`

## Purpose

This document defines what training artifacts should be saved after a successful model run and how those artifacts should be named.

The goal is to keep artifact outputs:

- simple;
- reusable for local inference;
- compatible with the shared scikit-learn pipeline design;
- easy to version without overcomplicating the first iteration.

## V1 Decision

The first implementation should save two canonical model artifacts:

- `models/pass_model.joblib`
- `models/accuracy_model.joblib`

These artifacts should be fitted scikit-learn `Pipeline` objects, not just raw estimators.

## Planned Artifact List

### `models/pass_model.joblib`

Purpose:

- saved classifier artifact for pass/fail prediction

Expected contents:

- the fitted shared preprocessing pipeline
- the fitted `RandomForestClassifier`
- feature-order and encoder state embedded inside the pipeline object

Prediction target:

- `target_passed`

Intended inference usage:

- `predict_proba`
- optionally `predict`

### `models/accuracy_model.joblib`

Purpose:

- saved regressor artifact for predicted accuracy

Expected contents:

- the fitted shared preprocessing pipeline
- the fitted `RandomForestRegressor`
- feature-order and encoder state embedded inside the pipeline object

Prediction target:

- `target_accuracy`

Intended inference usage:

- `predict`

## Why Save Full Pipelines

Save the full fitted scikit-learn `Pipeline`, not only the final estimator.

Reason:

- preprocessing must be identical between training and inference
- one-hot encoding state must be preserved
- model loading should not require reimplementing feature transformations manually

This is already consistent with the shared preprocessing design in `docs/preprocessing_pipeline.md`.

## Save Format

Chosen format:

- `joblib`

Reason:

- standard for scikit-learn model persistence
- suitable for full `Pipeline` objects
- easy to load locally in scripts or notebooks

## Recommended Directory Layout

V1 should save model artifacts under:

```text
models/
```

Planned canonical files:

```text
models/
  pass_model.joblib
  accuracy_model.joblib
```

This keeps the public artifact interface stable and easy to reference.

## Metadata And Versioning Notes

The canonical `.joblib` filenames should stay stable, but a training run should also save lightweight metadata describing what those files represent.

Recommended companion metadata file:

- `models/model_metadata.json`

Recommended metadata fields:

- artifact version string
- training timestamp
- source processed dataset path
- split strategy name
- split seed
- feature column list
- target name
- estimator class name
- primary evaluation metric name
- primary evaluation metric value
- supporting metrics summary

## Versioning Strategy

V1 versioning should be simple:

- keep stable canonical artifact names for the latest local models
- record run-specific details in `model_metadata.json`
- if needed later, copy or archive run-specific model files under a separate run directory rather than changing the public canonical filenames

Recommended artifact version label for the first implementation:

- `v1`

This avoids naming chaos while still leaving room for later experiment archiving.

## What Should Not Be Saved In V1

Do not require these as first-class saved artifacts yet:

- separate pickled preprocessors outside the final pipelines
- raw NumPy feature matrices
- per-fold intermediate models
- multiple threshold-tuned classifier variants
- framework-specific exports such as ONNX

Reason:

- they increase artifact noise
- they are not needed for the first local training and inference workflow

## Relationship To Current Docs

This artifact plan is consistent with:

- `docs/preprocessing_pipeline.md`
- `docs/processed_dataset_outputs.md`
- `docs/baseline_classifier.md`
- `docs/baseline_regressor.md`

## V1 Practical Recommendation

After each successful training run:

- save the fitted classifier pipeline to `models/pass_model.joblib`
- save the fitted regressor pipeline to `models/accuracy_model.joblib`
- save run metadata to `models/model_metadata.json`

This is enough structure for local reuse, evaluation traceability, and later iteration.
