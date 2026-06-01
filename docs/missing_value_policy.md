# Missing-Value Handling Rules

Project: `osu-skill-predictor`

## Purpose

This document defines how missing values should be handled before model training for the V1 `osu` dataset.

It answers three questions:

- which missing values make a row invalid;
- which missing values may be defaulted or imputed;
- which optional fields may be kept as missing without blocking training.

This policy applies to the flattened dataset produced by the collector under `data/raw/` and to the tracked sample file under `data/sample/` when it is used for local pipeline checks.

## General Principles

### Raw export vs training table

The raw exported dataset should preserve source missingness wherever practical.

That means:

- the collector should not silently invent values for API fields that were absent;
- defaulting and imputation decisions should be explicit in downstream processing;
- rejection rules should be deterministic and documented.

### Preferred order of handling

Use this order when a value is missing:

1. Keep the row if the field is optional and the model can safely ignore or impute it later.
2. Impute the field if the missingness is expected and the imputation is simple and low-risk.
3. Reject the row if the missing field breaks label integrity, entity identity, or core feature usability.

### V1 modeling bias

For V1, prefer conservative row rejection for missing labels and missing core beatmap or user features.

Do not rescue structurally broken rows with aggressive imputation. The first baseline should optimize for clean training data, not maximum row retention.

## Policy by Feature Group

### Identity and timestamps

| Column group | Examples | Missing-value policy | Reason |
|---|---|---|---|
| Stable row identity | `row_id` | reject row | Required for row tracking and deduplication. |
| Source entity IDs | `score_id`, `user_id`, `beatmap_id`, `beatmapset_id` | reject row | Missing IDs make joins and lineage invalid. |
| Ruleset | `ruleset` | reject row | V1 is `osu` only; missing ruleset breaks scope control. |
| Collection timestamps | `collected_at`, `score_created_at` | reject row | Needed for provenance, recency checks, and debugging. |

Decision summary:

- no imputation
- no defaulting
- any row missing one of these fields is invalid

### Labels and score-source context

| Column group | Examples | Missing-value policy | Reason |
|---|---|---|---|
| Classification label | `target_passed` | reject row | Cannot train or evaluate pass prediction without the label. |
| Regression label | `target_accuracy` | reject row | Cannot train or evaluate accuracy prediction without the label. |
| Score source | `score_source` | reject row | Needed to track label-source mix and bias between `recent` and `best`. |
| Mods string | `mods_raw` | default to empty string | Empty mod string is a valid representation of `No Mod`. |
| Score grade | `score_rank` | keep missing | Useful for analysis only; not required for V1 training. |

Decision summary:

- `target_passed`, `target_accuracy`, and `score_source` are hard-required
- `mods_raw` may be defaulted to `""`
- optional score outcome fields may remain missing

### Country-seeding context

| Column group | Examples | Missing-value policy | Reason |
|---|---|---|---|
| Country seed identity | `seed_country_code` | reject row | Required to understand sampling provenance. |
| Country ranking position | `seed_country_rank` | reject row | Required to reproduce or audit the sampling setup. |
| Country-local player rank | `seed_country_player_rank` | reject row | Required to understand which slice of a country ladder was sampled. |
| Seeded global rank | `seed_global_rank` | reject row | Important for downstream bias analysis and player-strength context. |

Decision summary:

- no imputation
- no defaulting
- all country-seeding fields are required for V1 provenance

### Player snapshot features

| Column group | Examples | Missing-value policy | Reason |
|---|---|---|---|
| Core player features | `user_pp`, `user_accuracy`, `user_play_count` | reject row | These are part of the minimum usable player-state snapshot for V1. |
| Extended ranking context | `user_global_rank`, `user_country_rank` | keep missing | Helpful but not essential; some profiles may legitimately omit or hide rank-related fields. |
| Extended play history | `user_play_time_sec`, `user_total_hits`, `user_maximum_combo` | keep missing initially; median-impute if used by a model | Useful but optional in the first baseline. |

Decision summary:

- missing `user_pp`, `user_accuracy`, or `user_play_count` invalidates the row
- optional player snapshot columns may remain null in raw data
- if optional player columns are selected into a model matrix, impute them explicitly during preprocessing

Recommended V1 imputation for optional numeric player columns:

- median imputation within the training split
- add a companion missing-indicator feature if missingness rate is non-trivial

### Beatmap features

| Column group | Examples | Missing-value policy | Reason |
|---|---|---|---|
| Core beatmap difficulty | `beatmap_star_rating`, `beatmap_bpm`, `beatmap_ar`, `beatmap_od`, `beatmap_cs` | reject row | These are central to the beatmap-side difficulty representation. |
| Core beatmap length | `beatmap_hit_length_sec`, `beatmap_total_length_sec` | reject row | Important for both modeling and validation consistency. |
| Beatmap popularity | `beatmap_passcount`, `beatmap_playcount` | reject row in V1 | These were explicitly kept in the schema and should be present if the row is considered valid. |
| Extended beatmap structure | `beatmap_hp`, `beatmap_count_circles`, `beatmap_count_sliders`, `beatmap_count_spinners`, `beatmap_status` | keep missing initially; impute only if used | Useful but not required to start training. |

Decision summary:

- missing core beatmap features invalidates the row
- optional beatmap structure fields may remain null in raw data
- if optional numeric beatmap columns are used later, median-impute in preprocessing
- if `beatmap_status` is used later, impute with explicit category `unknown`

### Score outcome diagnostics

| Column group | Examples | Missing-value policy | Reason |
|---|---|---|---|
| Outcome diagnostics | `observed_pp`, `observed_max_combo`, `count_300`, `count_100`, `count_50`, `count_miss` | keep missing initially; do not reject row | These are useful enrichments, but not mandatory for the first baseline. |

Decision summary:

- do not reject rows solely because these columns are missing
- if these columns are selected for a model:
  - numeric count fields may be defaulted to `0` only when missingness is known to mean "not reported"
  - otherwise use split-local median imputation plus missing indicators

Conservative V1 rule:

- prefer median imputation over `0` for `observed_pp` and `observed_max_combo`
- use `0` defaults for hit-count fields only if dataset inspection confirms the collector/API uses absent counts as structural zeros rather than missing data

### Optional mod-aware difficulty features

| Column group | Examples | Missing-value policy | Reason |
|---|---|---|---|
| Mod-aware beatmap attributes | `modded_star_rating`, `modded_max_combo` | keep missing | These fields are optional in the current collector design. |

Decision summary:

- no row rejection
- keep null in raw data when the beatmap-attributes endpoint was not queried
- if included in later modeling, either:
  - impute from the corresponding base beatmap feature; or
  - drop the column from the model matrix until the collector provides good coverage

Preferred V1 fallback:

- `modded_star_rating` -> fallback to `beatmap_star_rating`
- `modded_max_combo` -> keep missing or exclude from the model unless coverage improves

## Drop vs Impute Decisions

### Hard-drop row conditions

Drop the entire row if any of these are missing:

- `row_id`
- `score_id`
- `user_id`
- `beatmap_id`
- `beatmapset_id`
- `ruleset`
- `collected_at`
- `score_created_at`
- `score_source`
- `target_passed`
- `target_accuracy`
- `seed_country_code`
- `seed_country_rank`
- `seed_country_player_rank`
- `seed_global_rank`
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

### Safe defaults

Default these fields at raw-to-training preprocessing time:

- `mods_raw` -> empty string `""`
- optional categorical fields such as `beatmap_status` -> `unknown` only if that column is actively used

### Impute, but keep the row

These fields may be imputed later if included in the model:

- `user_global_rank`
- `user_country_rank`
- `user_play_time_sec`
- `user_total_hits`
- `user_maximum_combo`
- `beatmap_hp`
- `beatmap_count_circles`
- `beatmap_count_sliders`
- `beatmap_count_spinners`
- `observed_pp`
- `observed_max_combo`
- `count_300`
- `count_100`
- `count_50`
- `count_miss`
- `modded_star_rating`
- `modded_max_combo`

Recommended V1 imputation methods:

- numeric continuous features: median imputation within the training split
- optional categorical features: explicit `unknown`
- highly sparse optional features: drop the column from the model matrix instead of imputing if coverage is poor

## Invalid-Row Handling

### Row rejection policy

If a row violates any hard-required missingness rule:

- remove it from the training-ready dataset
- count it in a validation report
- preserve the reason for removal if an automated validation script exists

### Recommended rejection reason labels

When validation becomes scripted, use explicit reasons such as:

- `missing_identity_field`
- `missing_label`
- `missing_sampling_context`
- `missing_core_player_feature`
- `missing_core_beatmap_feature`
- `missing_timestamp`

### Thresholds for dataset-level failure

The pipeline should not silently proceed if row rejection is widespread.

Recommended V1 thresholds:

- if any hard-required column is entirely missing, fail the dataset immediately
- if more than `1%` of rows fail because of missing hard-required fields, flag the run for investigation
- if more than `5%` of rows fail because of missing hard-required fields, reject the run for training until the collector or parser issue is understood

## Validation Checklist for Missingness

Before training:

1. Confirm all hard-required columns exist.
2. Confirm hard-required columns have no null values.
3. Confirm `mods_raw` is non-null after defaulting empty strings.
4. Measure null rates for all optional player fields.
5. Measure null rates for all optional beatmap fields.
6. Measure null rates for all optional score diagnostic fields.
7. Decide which optional columns are included in the first model matrix.
8. For every included optional column, define the exact imputation rule in code.
9. Add missing-indicator columns for optional numeric fields if missingness is informative.
10. Record row-drop counts and reasons in the run report.

## V1 Practical Recommendation

For the first model-training pass:

- use only rows with complete hard-required fields
- keep `mods_raw` defaulted to empty string when absent
- start with the required feature set plus only low-missing optional features
- defer sparse optional columns until a profiling pass confirms they are worth keeping

This keeps the first baseline simple and reduces the risk of training on noisy, partially reconstructed rows.
