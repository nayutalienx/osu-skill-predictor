# Evaluation Metrics

Project: `osu-skill-predictor`

## Purpose

This document defines the first evaluation metrics for the MVP classifier and regressor.

The goal is to keep the metrics:

- understandable;
- sufficient for a first portfolio-quality iteration;
- aligned with the current dataset and baseline models.

## V1 Decision

Two model tracks are evaluated:

- classification for `target_passed`
- regression for `target_accuracy`

Primary metrics:

- classifier primary metric: `PR AUC`
- regressor primary metric: `MAE`

Secondary metrics are also tracked so the first baseline is not judged from a single number only.

## Classification Metrics

Classification target:

- `target_passed`

Recommended V1 classification metrics:

- `PR AUC`
- `ROC AUC`
- `F1`
- `precision`
- `recall`

### Primary classification metric

Chosen primary metric:

- `PR AUC`

Reason:

- the pass/fail target is imbalanced
- the project cares about correctly identifying likely passes without hiding poor minority-class performance behind a single broad accuracy number
- `PR AUC` is easier to defend than plain accuracy when positive-class coverage matters

### Supporting classification metrics

`ROC AUC`:

- useful as a threshold-independent ranking metric
- kept as a secondary metric because it can look overly optimistic on imbalanced problems

`F1`:

- useful as a single-threshold balance between precision and recall
- helps compare practical operating points after probability predictions are converted into labels

`precision` and `recall`:

- reported separately so errors are easier to interpret
- useful when a threshold decision later needs tuning for product behavior

### Why plain accuracy is not primary

Plain accuracy is easy to understand, but it is not the main V1 metric because:

- the dataset has a meaningful class imbalance
- a model can look acceptable on accuracy while still failing on the pass class

Accuracy can still be reported later as an auxiliary descriptive metric, but it is not the main baseline score.

## Regression Metrics

Regression target:

- `target_accuracy`

Target scale:

- percentage points on a `0` to `100` scale

Recommended V1 regression metrics:

- `MAE`
- `RMSE`
- `R²`

### Primary regression metric

Chosen primary metric:

- `MAE`

Reason:

- it is easy to explain in the native target units
- it directly answers how many percentage points the prediction is off on average
- it is less sensitive to a small number of large misses than `RMSE`

Interpretation example:

- `MAE = 4.8` means the model is off by about `4.8` accuracy percentage points on average

### Supporting regression metrics

`RMSE`:

- reported because it penalizes large misses more strongly than `MAE`
- useful for checking whether the model occasionally makes very bad predictions

`R²`:

- reported as a familiar goodness-of-fit summary
- treated as secondary because it is less intuitive than absolute error in this product context

## Metric Reporting Rules

For the first baseline iteration:

- always report the primary metric first
- also report the chosen secondary metrics in the same evaluation summary
- compute all metrics on the held-out test split only
- use the already documented grouped split by `user_id`

This keeps comparisons reproducible across future model runs.

## Mapping by Model

Classifier:

- model: `RandomForestClassifier`
- target: `target_passed`
- primary metric: `PR AUC`
- supporting metrics: `ROC AUC`, `F1`, `precision`, `recall`

Regressor:

- model: `RandomForestRegressor`
- target: `target_accuracy`
- primary metric: `MAE`
- supporting metrics: `RMSE`, `R²`

## V1 Practical Recommendation

For the first portfolio-quality baseline report:

- judge the classifier primarily by `PR AUC`
- judge the regressor primarily by `MAE`
- include the supporting metrics so failure modes stay visible

This is simple enough for an MVP and strong enough for later model comparisons.
