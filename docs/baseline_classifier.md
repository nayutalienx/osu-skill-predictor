# Baseline Classifier

Project: `osu-skill-predictor`

## Purpose

This document selects the first baseline classification model for the MVP.

It answers three questions:

- which scikit-learn classifier should be used first;
- why that classifier is a reasonable baseline;
- which inputs and target it should consume.

## V1 Decision

Chosen baseline classifier:

- `RandomForestClassifier`

Recommended initial configuration:

- use a standard scikit-learn `Pipeline`
- keep numeric features unscaled
- use the current categorical strategy:
  - one-hot encode `length_bucket`
  - pass helper booleans as `0/1`
- start with a class-balance-aware configuration, for example `class_weight="balanced"`

This is the first baseline choice, not the final model choice.

## Why This Model Was Chosen

### It matches the current preprocessing decisions

The repo already decided:

- no mandatory numeric scaling in the shared default path
- one-hot for low-cardinality categoricals
- boolean helper features as `0/1`

`RandomForestClassifier` fits that setup well because:

- it does not require feature scaling
- it works naturally with mixed numeric and one-hot encoded tabular features
- it handles nonlinear interactions better than a plain linear baseline

### It is simple enough for a first baseline

This is a good MVP baseline because it is:

- available directly in scikit-learn
- easy to train locally
- easy to evaluate with standard classification metrics
- robust to mixed feature ranges and simple engineered features

### It is easier to defend than a more complex boosted model

The first baseline should not start with a tuning-heavy estimator.

Compared with stronger but more complex options:

- it is simpler than gradient boosting workflows
- it is less sensitive to scaling than logistic regression
- it gives a more realistic nonlinear baseline for player-map interactions than a purely linear classifier

## Target Mapping

Classification target:

- `target_passed`

Interpretation:

- `true`: the player passed the beatmap on the observed score event
- `false`: the player failed the beatmap on the observed score event

This is a binary classification problem.

## Input Feature Mapping

The baseline classifier should use the cleaned and feature-ready training dataset, not the raw export directly.

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

Do not feed these directly into the baseline classifier:

- `row_id`
- `score_id`
- `user_id`
- `beatmap_id`
- `beatmapset_id`
- `mods_raw`
- `seed_country_code`
- `score_source`
- `target_accuracy`

Reason:

- identifiers encourage memorization
- raw combined mod strings are intentionally replaced by helper features
- `score_source` is useful for analysis but should not be a core predictive input in the first baseline
- `target_accuracy` is the regression target, not a classifier feature

## Pipeline Shape

Recommended V1 classifier pipeline:

1. start from the processed training dataset
2. select baseline feature columns
3. numeric branch:
   - passthrough
4. boolean helper branch:
   - cast to `0/1`
   - passthrough
5. categorical branch:
   - `OneHotEncoder(handle_unknown="ignore")` for `length_bucket`
6. classifier:
   - `RandomForestClassifier`

This keeps the baseline aligned with the existing preprocessing decisions.

## Why Not Logistic Regression First

`LogisticRegression` is still a valid comparison model later, but it is not the first baseline choice here.

Reasons:

- the project already expects nonlinear player-map interactions
- feature scales are mixed, so logistic regression would want a model-specific scaling branch immediately
- the first baseline should be useful without forcing scaling into the shared default pipeline

That does not make logistic regression wrong.

It just makes it a better comparison model after the tree baseline exists.

## Evaluation Readiness

This classifier is easy to evaluate with the planned split strategy:

- grouped train/test split by `user_id`
- binary target `target_passed`
- standard metrics such as accuracy, F1, ROC AUC, and PR AUC can be added later

## V1 Practical Recommendation

For the first baseline classifier run:

- use `RandomForestClassifier`
- keep shared numeric preprocessing as passthrough
- use the currently documented helper and categorical features
- treat this model as the first reference point before comparing linear or boosted alternatives

This gives the project a practical, explainable, scikit-learn-native starting classifier.
