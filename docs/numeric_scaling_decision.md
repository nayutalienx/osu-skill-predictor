# Numeric Scaling Decision

Project: `osu-skill-predictor`

## Purpose

This document defines whether numeric scaling should be part of the default preprocessing path for V1 candidate models.

It answers three questions:

- whether scaling is required by default;
- how the decision depends on likely baseline estimators;
- what the decision implies for the shared preprocessing pipeline.

## V1 Decision

The V1 default should be:

- no mandatory numeric scaling in the shared default preprocessing path

But:

- scaling should remain an optional branch for scale-sensitive estimators

This means:

- the default baseline preprocessing should pass numeric features through unchanged
- if a later candidate model requires or benefits strongly from scaling, enable scaling inside that model-specific pipeline rather than imposing it globally on every model

## Why This Decision Was Chosen

The current feature set is mostly:

- bounded or interpretable numeric profile summaries
- bounded beatmap difficulty values
- count-style popularity and experience statistics
- simple helper booleans

The first likely baseline estimators for this project are likely to be models such as:

- tree-based classifier or regressor
- linear or logistic baseline

These families behave differently with respect to scaling.

A global always-scale rule would add complexity to the default path before there is strong evidence it helps the first baseline.

## Estimator-Specific Reasoning

### Tree-based estimators

Examples:

- `RandomForestClassifier`
- `RandomForestRegressor`
- gradient-boosted tree models if introduced later

Scaling decision:

- scaling is not required

Reason:

- tree splits are based on order and thresholding, not Euclidean distance
- monotonic rescaling usually does not materially change their behavior
- leaving numeric features in original units preserves interpretability

### Linear and logistic estimators

Examples:

- `LogisticRegression`
- `Ridge`
- `Lasso`
- `ElasticNet`

Scaling decision:

- scaling is recommended if one of these becomes the main baseline

Reason:

- coefficient regularization is sensitive to feature scale
- optimization is often more stable when numeric features are standardized
- unscaled high-range features can dominate low-range features in regularized linear models

### Distance-based estimators

Examples:

- `KNeighborsClassifier`
- `KNeighborsRegressor`
- SVM variants if introduced later

Scaling decision:

- scaling is strongly recommended

Reason:

- distance-based models are directly sensitive to absolute feature scale
- raw count-like columns can overwhelm bounded feature scales otherwise

### Naive Bayes or rule-style baselines

Scaling decision:

- depends on the exact implementation
- not the main driver of the V1 default choice

## V1 Likely Baseline Implication

For the first portfolio-quality baseline, the project should prefer one of:

- a tree-based baseline first; or
- a simple linear/logistic baseline as a comparison model

Given that likely path, the best default is:

- do not force scaling globally
- allow scaling as an optional numeric branch when testing scale-sensitive models

This avoids making the entire pipeline more complex just to support one family of estimators.

## Shared Pipeline Implications

### Default shared preprocessing

Recommended default:

1. numeric columns
   - passthrough
2. boolean helper columns
   - cast to `0/1`
   - passthrough
3. low-cardinality categorical columns
   - `OneHotEncoder(handle_unknown="ignore")`

This matches the current categorical encoding strategy.

### Optional scaled numeric branch

When evaluating a scale-sensitive estimator, add:

- `StandardScaler()` on the numeric branch inside that estimator’s pipeline

Recommended pattern:

- keep one common column selection contract
- vary only the numeric transformer by model family

Example design:

- tree pipeline: numeric passthrough
- linear pipeline: numeric `StandardScaler()`

This keeps experiments comparable without pretending every model needs the same preprocessing.

## Why Not Min-Max Scaling by Default

V1 should not choose min-max scaling as the default.

Reason:

- it is less standard than z-score scaling for common linear baselines
- it can be more sensitive to outliers or future-range drift
- there is no strong V1 reason to prefer it

If scaling is needed, prefer:

- `StandardScaler()`

## Feature-Range Considerations

The current numeric feature set mixes:

- bounded scales such as `user_accuracy`, `beatmap_ar`, `beatmap_od`, `beatmap_cs`
- moderate-range values such as `beatmap_star_rating`
- larger-range count fields such as `beatmap_playcount`, `beatmap_passcount`, `user_play_count`

This mixed scale is exactly why:

- scaling may help linear or distance-based estimators
- scaling is unnecessary for tree-based baselines

## Leakage and Fit Discipline

If scaling is enabled for a model:

- fit the scaler on the training split only
- apply the fitted scaler to validation and test data
- never fit scaling on the full dataset before splitting

This should be handled through a scikit-learn `Pipeline` or `ColumnTransformer`, not by ad hoc dataframe mutation.

## Summary Table

| Estimator family | Scaling decision |
|---|---|
| Tree-based models | not needed |
| Linear / logistic models | recommended |
| Distance-based models | strongly recommended |
| Shared V1 default preprocessing | no mandatory scaling |

## V1 Practical Recommendation

For the first baseline phase:

- default numeric preprocessing: passthrough
- keep scaling out of the mandatory shared preprocessing path
- if a linear or distance-based comparison model is tested, add `StandardScaler()` inside that model’s pipeline only

This keeps the default preprocessing simple while still supporting fair model comparisons later.
