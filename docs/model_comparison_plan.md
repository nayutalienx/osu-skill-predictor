# Model Comparison Plan

Project: `osu-skill-predictor`

## Purpose

This document defines a small, controlled model comparison pass for the MVP.

The goal is to compare a few reasonable classical models without turning the project into tuning-heavy research.

## V1 Decision

The first comparison pass should be:

- small;
- reproducible;
- limited to scikit-learn models;
- evaluated on the already documented grouped train/test split by `user_id`.

This comparison pass is meant to answer:

- whether the baseline random-forest models are competitive enough to keep;
- whether a simpler linear model is clearly worse or still viable;
- whether a lightweight boosted/tree alternative is worth carrying forward.

## Candidate Model List

### Classification candidates

- `RandomForestClassifier`
- `LogisticRegression`
- `HistGradientBoostingClassifier`

### Regression candidates

- `RandomForestRegressor`
- `Ridge`
- `HistGradientBoostingRegressor`

## Why These Candidates

`RandomForestClassifier` and `RandomForestRegressor`:

- these are the documented baseline models
- they are the anchor models for the first comparison

`LogisticRegression`:

- gives a simple linear classification reference point
- helps measure how much nonlinear interaction modeling actually matters

`Ridge`:

- gives a simple linear regression reference point
- is more stable than plain unregularized linear regression for tabular work

`HistGradientBoostingClassifier` and `HistGradientBoostingRegressor`:

- provide a stronger tree-based comparison without leaving scikit-learn
- are still manageable for local experimentation
- are a reasonable next step without introducing external boosting libraries yet

## Comparison Rules

To keep the pass small and fair:

- use the same processed dataset for all candidates
- use the same grouped train/test split for all candidates
- use the same feature set for all candidates unless a model requires a documented exception
- use the same primary metric family already defined for each task
- avoid broad hyperparameter searches in this phase

### Classification comparison criteria

Primary comparison metric:

- `PR AUC`

Supporting classification criteria:

- `ROC AUC`
- `F1`
- training time
- inference simplicity

### Regression comparison criteria

Primary comparison metric:

- `MAE`

Supporting regression criteria:

- `RMSE`
- `R²`
- training time
- inference simplicity

## Preprocessing Expectations By Model Family

Tree-based candidates:

- `RandomForestClassifier`
- `RandomForestRegressor`
- `HistGradientBoostingClassifier`
- `HistGradientBoostingRegressor`

Expected preprocessing:

- shared documented preprocessing pipeline
- no mandatory numeric scaling

Linear candidates:

- `LogisticRegression`
- `Ridge`

Expected preprocessing:

- same feature selection as the baseline
- add model-specific numeric scaling inside the model pipeline

This keeps the comparison fair without forcing global scaling onto all models.

## Recommended Initial Scope

For the first pass, compare exactly:

Classifier side:

- baseline: `RandomForestClassifier`
- linear comparison: `LogisticRegression`
- boosted comparison: `HistGradientBoostingClassifier`

Regressor side:

- baseline: `RandomForestRegressor`
- linear comparison: `Ridge`
- boosted comparison: `HistGradientBoostingRegressor`

No additional models should be added unless one of these results reveals a clear reason to expand the search.

## Overfitting And Dataset-Size Caveats

### Attempt-level rows are correlated

The dataset is attempt-level and grouped by player.

That means:

- multiple rows can still share the same beatmap
- repeated patterns can make flexible models look stronger than they really are

This is one reason the grouped split by `user_id` is already required.

### Tree models can overfit faster than linear models

Random forests and boosted trees can fit complex interactions quickly.

That is useful, but it also means:

- train metrics may look much better than test metrics
- small gains on the test split may not justify a more complex model

The comparison pass should explicitly watch for large train-test gaps.

### The dataset is large enough for a baseline pass, but not infinite

The current dataset is substantial, but the project still should not treat one split result as final truth.

Important caveats:

- the sampled players are still shaped by the chosen collection strategy
- country-seeded sampling can introduce coverage bias
- some models may benefit from more data rather than more tuning

### Do not confuse comparison with tuning

This phase is not for exhaustive optimization.

Avoid:

- large grid searches
- repeated manual metric fishing
- model-by-model bespoke feature engineering

The point is to establish a sensible ranking of a few candidates, not to squeeze out the last fraction of performance.

## Decision Rule After The Comparison Pass

At the end of the small comparison pass:

- keep the current baseline if it is competitive and simpler to defend
- upgrade only if another candidate shows a clear and repeatable improvement on the primary metric
- prefer the simpler model when performance differences are marginal

## V1 Practical Recommendation

Run one controlled comparison pass across:

- `RandomForestClassifier`, `LogisticRegression`, `HistGradientBoostingClassifier`
- `RandomForestRegressor`, `Ridge`, `HistGradientBoostingRegressor`

Judge them primarily by:

- `PR AUC` for classification
- `MAE` for regression

Keep the process small, reproducible, and resistant to overfitting-by-experimentation.
