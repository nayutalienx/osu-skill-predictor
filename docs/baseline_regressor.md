# Baseline Regressor

Project: `osu-skill-predictor`

## Purpose

This document selects the first baseline regression model for the MVP.

It answers three questions:

- which scikit-learn regressor should be used first;
- why that regressor is a reasonable baseline;
- what target scale and input features it should use.

## V1 Decision

Chosen baseline regressor:

- `RandomForestRegressor`

Recommended initial configuration:

- use a standard scikit-learn `Pipeline`
- keep numeric features unscaled
- use the current categorical strategy:
  - one-hot encode `length_bucket`
  - pass helper booleans as `0/1`
- keep the first run simple and avoid heavy tuning

This is the first regression baseline, not the final model choice.

## Why This Model Was Chosen

### It matches the classifier choice

The current baseline classifier is:

- `RandomForestClassifier`

Using `RandomForestRegressor` for the accuracy target keeps the MVP coherent:

- same general model family
- same default preprocessing assumptions
- same mixed-feature compatibility
- lower cognitive overhead for the first end-to-end training pipeline

### It matches the preprocessing decisions

The repo already decided:

- no mandatory numeric scaling in the shared default preprocessing path
- one-hot for low-cardinality categoricals
- boolean helper features as `0/1`

`RandomForestRegressor` fits that setup well because:

- it does not require feature scaling
- it handles mixed numeric and one-hot encoded inputs naturally
- it can capture nonlinear interactions between player and beatmap features

### It is simple enough for a first regression baseline

This is a good MVP baseline because it is:

- available directly in scikit-learn
- easy to train locally
- easy to compare against later alternatives
- robust to raw feature ranges and simple engineered features

## Target Mapping

Regression target:

- `target_accuracy`

Interpretation:

- predicted accuracy percentage for the observed attempt

Expected output scale:

- `0` to `100`

Important note:

- the model is trained on a target stored as percentage points, not on a `0` to `1` fraction

### Practical prediction note

Tree regressors can occasionally predict values slightly outside the natural domain if later model families change or postprocessing differs, but for V1 the intended business/domain interpretation remains:

- lower bound: `0`
- upper bound: `100`

Recommended inference-side safety behavior:

- clip final reported predictions into `[0, 100]` if needed

## Input Feature Mapping

The baseline regressor should use the cleaned and feature-ready training dataset, not the raw export directly.

### Numeric player features

- `user_pp`
- `user_accuracy`
- `user_play_count`

### Numeric beatmap features

- `beatmap_star_rating`
- `beatmap_bpm`
- `beatmap_ar`
- `beatmap_od`
- `beatmap_cs`
- `beatmap_hit_length_sec`
- `beatmap_total_length_sec`
- `beatmap_passcount`
- `beatmap_playcount`

### Engineered interaction feature

- `star_gap`

### Helper boolean features

- `has_hidden`
- `has_hardrock`
- `has_doubletime`

### Low-cardinality categorical feature

- `length_bucket`

## Explicit Exclusions From the Baseline Feature Matrix

Do not feed these directly into the baseline regressor:

- `row_id`
- `score_id`
- `user_id`
- `beatmap_id`
- `beatmapset_id`
- `mods_raw`
- `seed_country_code`
- `score_source`
- `target_passed`

Reason:

- identifiers encourage memorization
- raw combined mod strings are intentionally replaced by helper features
- `score_source` is analysis metadata rather than a core inference input
- `target_passed` is the classification target and should not leak into the regression model

## Pipeline Shape

Recommended V1 regressor pipeline:

1. start from the processed training dataset
2. select baseline feature columns
3. numeric branch:
   - passthrough
4. boolean helper branch:
   - cast to `0/1`
   - passthrough
5. categorical branch:
   - `OneHotEncoder(handle_unknown="ignore")` for `length_bucket`
6. regressor:
   - `RandomForestRegressor`

This keeps the regression baseline aligned with the current preprocessing decisions.

## Why Not Linear Regression First

`LinearRegression` or `Ridge` are still valid comparison models later, but they are not the first baseline choice here.

Reasons:

- the project already expects nonlinear player-map interactions
- mixed feature scales would immediately make scaling a more central concern
- the first baseline should align with the current no-mandatory-scaling default path

That does not make linear regression wrong.

It just makes it a better comparison model after the tree baseline exists.

## Evaluation Readiness

This regressor is easy to evaluate with the planned split strategy:

- grouped train/test split by `user_id`
- target `target_accuracy` on a `0` to `100` scale

Appropriate later metrics include:

- MAE
- RMSE
- R²

## V1 Practical Recommendation

For the first baseline regressor run:

- use `RandomForestRegressor`
- keep shared numeric preprocessing as passthrough
- use the currently documented helper and categorical features
- treat this model as the first reference point before comparing linear or boosted regression alternatives

This gives the project a practical, scikit-learn-native starting regressor for predicted accuracy.
