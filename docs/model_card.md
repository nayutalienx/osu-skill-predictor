# Model Card

Project: `osu-skill-predictor`

## Model Scope

This project predicts, for osu! standard:

- pass probability for a player-beatmap attempt
- expected accuracy percentage for that attempt

It is a tabular classical ML system using saved scikit-learn pipelines.

## Current Canonical Models

Classifier:

- `RandomForestClassifier`

Regressor:

- `HistGradientBoostingRegressor`

These are saved as:

- `models/pass_model.joblib`
- `models/accuracy_model.joblib`

## Intended Use

Good fit:

- local experimentation
- portfolio demonstration
- rough player-vs-map prediction from compact tabular features

Not intended for:

- competitive ranking decisions
- real-time gameplay adaptation
- replay-level or event-stream analysis
- highly personalized long-history recommendation systems

## Input Features

Main player summary inputs:

- `user_pp`
- `user_accuracy`
- `user_play_count`

Main beatmap summary inputs:

- `beatmap_star_rating`
- `beatmap_bpm`
- `beatmap_ar`
- `beatmap_od`
- `beatmap_cs`
- `beatmap_hit_length_sec`
- `beatmap_total_length_sec`
- `beatmap_passcount`
- `beatmap_playcount`

Mod input:

- `mods_raw`

Internally engineered features include:

- `star_gap`
- `length_bucket`
- `has_hidden`
- `has_hardrock`
- `has_doubletime`

## Training Data

Current primary dataset:

- country-seeded sampled osu! API v2 attempt data

Stored run:

- `data/raw/osu_country_try_data_full_20260601T074107Z/`

Scale recorded in metadata:

- `184,229` cleaned rows
- `9,999` unique users
- `35,261` unique beatmaps

## Evaluation Summary

Primary comparison mode for current canonical model selection:

- grouped cross-validation by `user_id`

Selected winners:

- classifier winner by `PR AUC mean`: `RandomForestClassifier`
- regressor winner by `MAE mean`: `HistGradientBoostingRegressor`

Stored winner metrics in current metadata:

- classifier `pr_auc_mean`: about `0.9947`
- regressor `mae_mean`: about `3.4644`

## Important Interpretation Notes

- strong classifier metrics are helped by the dataset distribution and by repeated structural patterns in attempt data
- grouped splitting by `user_id` reduces leakage, but it does not remove every possible map-level overlap effect
- the regressor output is clipped into `[0, 100]` at API inference time

## Main Limitations

- current player features are snapshots, not true historical values at play time
- dataset collection is sampled, not a full unbiased history of osu! attempts
- only `osu` standard is covered
- recommendation text is rule-based, not learned
- `star_gap` depends on a training-derived comfort mapping rather than a direct player historical comfort model

## Ethical And Practical Boundaries

This model should be treated as an approximate skill-support tool, not as a definitive judgment of player ability.

It can be useful for:

- quick estimation
- demo APIs
- baseline ML portfolio work

It should not be presented as an authoritative player skill evaluator.
