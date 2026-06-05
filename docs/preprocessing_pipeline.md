# Shared Scikit-Learn Preprocessing Pipeline

Project: `osu-skill-predictor`

## Purpose

This document defines the shared preprocessing pipeline design for the MVP.

The goal is to keep preprocessing:

- reproducible
- reusable between training and inference
- compatible with both the classifier and regressor baselines
- serializable with `joblib`

## V1 Decision

Use a scikit-learn `ColumnTransformer` wrapped inside model-specific `Pipeline` objects.

Core idea:

- one shared preprocessing design
- two final estimators:
  - one classifier pipeline
  - one regressor pipeline

This lets the project reuse the same feature preparation logic for both tasks while keeping the final model objects separate.

## Shared Pipeline Structure

Recommended high-level structure:

1. start from the processed training dataset
2. select baseline feature columns
3. apply a shared `ColumnTransformer`
4. attach the final estimator in a scikit-learn `Pipeline`

In conceptual form:

```python
Pipeline([
    ("preprocess", column_transformer),
    ("model", estimator),
])
```

## Preprocessing Steps

### 1. Column selection

The preprocessing layer should consume only the approved baseline feature columns.

### Numeric columns

Current recommended numeric columns:

- `user_pp`
- `user_accuracy`
- `user_play_count`
- `beatmap_star_rating`
- `beatmap_bpm`
- `beatmap_ar`
- `beatmap_od`
- `beatmap_cs`
- `beatmap_hit_length_sec`
- `beatmap_total_length_sec`
- `beatmap_passcount`
- `beatmap_playcount`
- `star_gap`

### Boolean helper columns

Current recommended boolean helper columns:

- `has_hidden`
- `has_hardrock`
- `has_doubletime`

### Low-cardinality categorical columns

Current recommended categorical columns:

- `length_bucket`

### Excluded columns

Do not feed these directly into the shared baseline pipeline:

- `row_id`
- `score_id`
- `user_id`
- `beatmap_id`
- `beatmapset_id`
- `mods_raw`
- `seed_country_code`
- `score_source`
- target columns

## 2. Numeric branch

Default V1 behavior:

- passthrough numeric features unchanged

Reason:

- current baseline models are tree-based
- the numeric scaling decision already says scaling should not be mandatory in the shared default path

Optional model-specific variation later:

- replace numeric passthrough with `StandardScaler()` for scale-sensitive comparison models

## 3. Boolean branch

Behavior:

- cast booleans to numeric `0/1`
- passthrough

Reason:

- these are already engineered interpretable binary indicators
- they do not need one-hot encoding

## 4. Categorical branch

Behavior:

- one-hot encode low-cardinality categorical columns

Recommended transformer:

- `OneHotEncoder(handle_unknown="ignore")`

Reason:

- `length_bucket` is a small stable categorical variable
- `handle_unknown="ignore"` makes inference more robust if training data did not contain every category

## Recommended `ColumnTransformer` Design

Conceptual structure:

```python
ColumnTransformer(
    transformers=[
        ("numeric", "passthrough", numeric_columns),
        ("boolean", "passthrough", boolean_columns),
        ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical_columns),
    ],
    remainder="drop",
)
```

Important note:

- if boolean columns are stored as Python booleans in pandas, that is acceptable
- if needed, a tiny preprocessing step may coerce them to `0/1` before the transformer or via a lightweight function transformer

## Training Reuse

This design supports local training reuse because:

- the exact same preprocessing object is fit every training run
- feature selection and encoding logic lives inside the pipeline, not in scattered notebook code
- train/test consistency is enforced automatically by scikit-learn once the pipeline is fit on the training split

Recommended training flow:

1. load processed training dataset
2. split rows using the saved split assignment
3. fit the full pipeline on training rows only
4. evaluate on held-out rows using the same fitted pipeline

## Inference Reuse

This design supports inference reuse because:

- the fitted preprocessing logic and model are bundled together
- no separate manual feature-transformation script is required at prediction time
- the same object can be loaded and called with `predict` or `predict_proba`

Expected inference flow:

1. build a one-row or batch dataframe with the same feature columns
2. load the serialized fitted pipeline
3. call:
   - classifier: `predict_proba` and optionally `predict`
   - regressor: `predict`

## Joblib Compatibility

This plan is compatible with `joblib` serialization because:

- `Pipeline` is serializable
- `ColumnTransformer` is serializable
- `OneHotEncoder` is serializable
- standard scikit-learn estimators such as random forests are serializable

Recommended artifact pattern:

- save one classifier pipeline artifact
- save one regressor pipeline artifact

Example future paths:

- `models/pass_model.joblib`
- `models/accuracy_model.joblib`

## Why This Design Is Preferable to Ad Hoc Notebook Logic

Avoid this anti-pattern:

- feature cleaning in one notebook cell
- one-hot encoding in another notebook
- estimator training in a separate script
- inference code reimplementing transformations manually

The shared pipeline design is better because:

- preprocessing is centralized
- training and inference use the same fitted logic
- leakage risk is lower
- behavior is easier to test

## Recommended Module Responsibilities

When implementation begins, a clean structure would be:

- one function that returns the shared `ColumnTransformer`
- one function that returns the classifier pipeline
- one function that returns the regressor pipeline

Conceptual split:

- `build_preprocessor()`
- `build_classifier_pipeline()`
- `build_regressor_pipeline()`

This keeps the estimator choice separate from the shared preprocessing contract.

## Relationship to Current Docs

This design is consistent with:

- [categorical_encoding_strategy.md](categorical_encoding_strategy.md)
- [numeric_scaling_decision.md](numeric_scaling_decision.md)
- [baseline_classifier.md](baseline_classifier.md)
- [baseline_regressor.md](baseline_regressor.md)

## V1 Practical Recommendation

For the first implementation:

- use one shared `ColumnTransformer`
- keep numeric columns as passthrough by default
- pass boolean helper features directly
- one-hot encode `length_bucket`
- wrap the transformer in separate classifier and regressor `Pipeline` objects
- serialize the fitted pipelines with `joblib`

This gives the project a simple, reproducible preprocessing foundation for both local training and local inference.
