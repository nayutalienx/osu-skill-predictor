# Raw Data Validation

Project: `osu-skill-predictor`

## Purpose

This document defines the minimum validation expectations for the first training dataset before feature engineering or model training begins.

It is focused on the flattened CSV output produced by the current collector, not on replay-level data or fully processed training artifacts.

## Validation Scope

Current primary dataset artifact:

- flattened CSV written into a run directory under `data/raw/`
- current default filename: `osu_country_try_data_v1.csv`

This validation spec applies to:

- the full API-backed dataset exported for training
- the small tracked sample file under `data/sample/` when used for local pipeline checks

## Required Columns

The raw dataset must contain at least these columns:

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
- `mods_raw`
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

If any required column is missing, the dataset should be treated as invalid for training.

## Expected Types and Value Domains

### Identity and timestamps

| Column | Expected dtype | Required domain / rule |
|---|---|---|
| `row_id` | string | non-empty, unique per row |
| `score_id` | integer | non-negative; duplicates should be investigated |
| `user_id` | integer | positive |
| `beatmap_id` | integer | positive |
| `beatmapset_id` | integer | positive |
| `ruleset` | string | must equal `osu` for V1 |
| `collected_at` | ISO 8601 datetime string | parseable timestamp |
| `score_created_at` | ISO 8601 datetime string | parseable timestamp |

### Labels and source fields

| Column | Expected dtype | Required domain / rule |
|---|---|---|
| `score_source` | string | expected values are `recent` or `best` |
| `target_passed` | boolean | must be `true` or `false` |
| `target_accuracy` | float | expected range `0` to `100` inclusive |
| `mods_raw` | string | may be empty; otherwise compact mod code string |

### Country-seeding context

| Column | Expected dtype | Required domain / rule |
|---|---|---|
| `seed_country_code` | string | two-letter country code expected |
| `seed_country_rank` | integer | positive |
| `seed_country_player_rank` | integer | positive and typically `<= 10000` under current collector |
| `seed_global_rank` | integer | positive |

### Player snapshot features

| Column | Expected dtype | Required domain / rule |
|---|---|---|
| `user_pp` | float | non-negative |
| `user_accuracy` | float | expected range `0` to `100` inclusive |
| `user_play_count` | integer | non-negative |

Optional but common player fields:

| Column | Expected dtype | Required domain / rule |
|---|---|---|
| `user_global_rank` | integer | positive when present |
| `user_country_rank` | integer | positive when present |
| `user_play_time_sec` | integer | non-negative when present |
| `user_total_hits` | integer | non-negative when present |
| `user_maximum_combo` | integer | non-negative when present |

### Beatmap features

| Column | Expected dtype | Required domain / rule |
|---|---|---|
| `beatmap_star_rating` | float | non-negative |
| `beatmap_bpm` | float | positive |
| `beatmap_ar` | float | expected practical range `0` to `12` |
| `beatmap_od` | float | expected practical range `0` to `12` |
| `beatmap_cs` | float | expected practical range `0` to `10` |
| `beatmap_hit_length_sec` | integer | non-negative |
| `beatmap_total_length_sec` | integer | non-negative and typically `>= beatmap_hit_length_sec` |
| `beatmap_passcount` | integer | non-negative |
| `beatmap_playcount` | integer | non-negative and typically `>= beatmap_passcount` |

Optional but common beatmap fields:

| Column | Expected dtype | Required domain / rule |
|---|---|---|
| `beatmap_hp` | float | expected practical range `0` to `12` when present |
| `beatmap_count_circles` | integer | non-negative when present |
| `beatmap_count_sliders` | integer | non-negative when present |
| `beatmap_count_spinners` | integer | non-negative when present |
| `beatmap_status` | string | ranked-status label when present |

### Score outcome details

| Column | Expected dtype | Required domain / rule |
|---|---|---|
| `score_rank` | string | grade label such as `F`, `A`, `S`, `SH`, `X`, `XH` when present |
| `observed_pp` | float | non-negative when present |
| `observed_max_combo` | integer | non-negative when present |
| `count_300` | integer | non-negative when present |
| `count_100` | integer | non-negative when present |
| `count_50` | integer | non-negative when present |
| `count_miss` | integer | non-negative when present |

## Minimum Dataset-Level Checks

These checks should pass before training starts.

### Structure checks

- the file exists and loads successfully
- the header contains all required columns
- no required column is duplicated under a different spelling or casing
- row count is greater than zero

### Type checks

- required numeric columns parse as numeric
- required boolean columns parse as booleans
- required timestamps parse as datetimes
- required string identifiers are non-empty

### Domain checks

- `ruleset` contains only `osu`
- `score_source` contains only allowed values
- `target_accuracy` stays within `0` to `100`
- `user_accuracy` stays within `0` to `100`
- required IDs are positive
- required count fields are non-negative

### Consistency checks

- `row_id` is unique
- `beatmap_total_length_sec >= beatmap_hit_length_sec`
- `beatmap_playcount >= beatmap_passcount`
- failed rows should not dominate because of parsing errors in `target_passed`
- `seed_country_player_rank <= country_ranking_max` for the run configuration that created the file

### Sampling checks

- sampled users are present for every intended country in the run
- `processed_user_count == sampled_user_count` for a completed run
- source mix across `recent` and `best` is recorded and inspected

## Recommended Raw Validation Checklist

Use this checklist before model training:

1. Confirm the run directory contains `config.json`, `state.json`, `export_metadata.json`, the flattened CSV, and `profiling_summary.md`.
2. Confirm the CSV loads locally without truncation or parser errors.
3. Confirm all required columns are present.
4. Confirm required numeric, boolean, and datetime fields parse correctly.
5. Confirm `row_id` uniqueness.
6. Confirm `ruleset == osu` for all rows.
7. Confirm `target_accuracy` and `user_accuracy` stay within `0` to `100`.
8. Confirm required IDs and count fields are non-negative and positive where expected.
9. Confirm country-seeding fields are populated for all rows.
10. Confirm the dataset has both target columns and the label values look plausible.
11. Confirm `processed_user_count` in `state.json` matches the intended sampled user count for a completed run.
12. Review `profiling_summary.md` for obvious anomalies in source mix, row counts, beatmap counts, and country coverage.

## Failure Handling

If validation fails:

- do not start model training on that dataset
- record which checks failed
- determine whether the issue is:
  - a collector bug
  - a parsing bug
  - an incomplete run
  - expected missingness in optional columns
- rebuild or filter the dataset only after the failure is understood

## Current Gaps

At this stage, validation is documented but not yet fully automated in a dedicated validation script.

That means:

- this document is the source of truth for what the raw dataset must satisfy
- an implementation task still remains to codify these checks in Python before training becomes routine
