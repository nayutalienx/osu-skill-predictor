# Categorical Encoding Strategy

Project: `osu-skill-predictor`

## Purpose

This document defines how categorical and mod-derived fields should enter the V1 training pipeline.

It answers three questions:

- which encoding approach should be used for the first baseline;
- how that approach fits a scikit-learn pipeline;
- which high-cardinality fields should be excluded or deferred.

## V1 Decision

Use a simple scikit-learn-compatible encoding strategy:

- numeric features: pass through unchanged for now
- boolean helper features: cast to `0/1` and pass through
- low-cardinality categorical features: one-hot encode
- raw high-cardinality identifiers and raw mod strings: do not feed directly into the baseline model

## Core Principle

The V1 baseline should favor interpretability and stability over clever encoding.

That means:

- avoid target encoding in the first iteration
- avoid frequency encoding in the first iteration
- avoid using raw IDs as features
- prefer helper features over raw combined categorical strings when possible

## Field-Level Strategy

### Boolean helper features

Fields:

- `has_hidden`
- `has_hardrock`
- `has_doubletime`

Encoding:

- convert to boolean or integer `0/1`
- pass through directly

Why:

- these features are already human-interpretable binary indicators
- no extra categorical expansion is needed

## Low-cardinality categorical features

### `length_bucket`

Encoding:

- one-hot encode

Recommended categories:

- `short`
- `medium`
- `long`

Why:

- it is a small closed set
- one-hot encoding preserves interpretability
- it works cleanly in scikit-learn pipelines

Recommended scikit-learn setting:

- `OneHotEncoder(handle_unknown="ignore")`

This keeps the pipeline robust if one category is absent in a training fold or if later data introduces edge cases.

### Optional future categorical fields

If these fields are added into a later baseline and their observed cardinality remains small, they may also use one-hot encoding:

- `beatmap_status`
- small derived categorical buckets created later

But they are not required for the first encoding contract.

## Raw Mod Field Strategy

### `mods_raw`

V1 decision:

- do not one-hot encode raw `mods_raw` directly in the first baseline

Reason:

- combined mod strings create a sparse and fragmented categorical space
- many combinations are rare
- raw strings like `HDHR`, `HDDT`, `HRDT`, `NC`, `EZHD`, and so on quickly increase feature sparsity

Use instead:

- `has_hidden`
- `has_hardrock`
- `has_doubletime`

Why this is better for V1:

- lower dimensionality
- more interpretable features
- fewer sparsity problems
- easier reuse at inference time

### Future option

If later experiments justify it, `mods_raw` could be:

- grouped into a smaller canonical mod-family category; or
- one-hot encoded after aggressive frequency filtering

But that is explicitly out of scope for the first baseline.

## High-Cardinality Fields and Risk Handling

### Fields that should not be directly encoded for V1

Do not directly one-hot encode or otherwise feed these raw identifiers into the baseline model:

- `row_id`
- `score_id`
- `user_id`
- `beatmap_id`
- `beatmapset_id`
- `seed_country_code`

Reasons:

- IDs are identifiers, not stable generalizable features
- one-hot encoding them would explode dimensionality
- they would encourage memorization instead of learning transferable patterns

### `seed_country_code`

V1 decision:

- exclude from the first baseline model matrix

Reason:

- while not as extreme as `user_id` or `beatmap_id`, it still introduces country-specific sampling structure that may not reflect the intended prediction contract
- it is better treated as analysis metadata first, not as a core predictive feature

Possible future revisit:

- include as one-hot only if later analysis shows country context materially improves generalization and does not just fit collector sampling artifacts

## Scikit-Learn Pipeline Compatibility

The chosen strategy is designed for a standard `ColumnTransformer` pipeline.

Recommended structure:

1. numeric columns branch
   - passthrough for now
2. boolean helper columns branch
   - cast to numeric `0/1`
   - passthrough
3. low-cardinality categorical columns branch
   - `OneHotEncoder(handle_unknown="ignore")`

This is compatible with:

- `Pipeline`
- `ColumnTransformer`
- `joblib` serialization
- train/test split discipline where preprocessing is fit only on the training split

## Recommended V1 Column Groups

### Numeric passthrough

Examples:

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
- `star_gap` when implemented

### Boolean passthrough

Examples:

- `has_hidden`
- `has_hardrock`
- `has_doubletime`

### One-hot encoded categorical

Examples:

- `length_bucket`

### Excluded from baseline matrix

Examples:

- `mods_raw`
- `row_id`
- `score_id`
- `user_id`
- `beatmap_id`
- `beatmapset_id`
- `seed_country_code`

## High-Cardinality Risk Summary

Relevant V1 high-cardinality risks:

- raw combined mod strings
- country codes if treated too literally
- direct entity IDs

Mitigation:

- use helper booleans instead of raw mod strings
- exclude IDs from the feature matrix
- keep country information as metadata unless later evidence supports its inclusion

## V1 Practical Recommendation

For the first baseline:

- one-hot encode `length_bucket`
- pass `has_hidden`, `has_hardrock`, and `has_doubletime` as booleans
- keep numeric columns numeric
- exclude raw `mods_raw` and all entity IDs from the model matrix
- use `OneHotEncoder(handle_unknown="ignore")` inside a scikit-learn `ColumnTransformer`

This keeps the categorical handling simple, interpretable, and production-friendly for the MVP.
