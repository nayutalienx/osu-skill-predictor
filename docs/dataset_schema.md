# Dataset Schema

Project: `osu-skill-predictor`

## Goal

Define the first-iteration training dataset schema for a classical ML service that:

- predicts whether an osu! player can pass a beatmap;
- predicts expected accuracy for that play.

This schema is intentionally scoped to the MVP and favors fields that are available from the official osu! API v2 without building a complex historical data pipeline.

## V1 Scope

- Ruleset: `osu` only
- Row granularity: one row per observed user score on one beatmap
- Main score source: recent user scores with failures included
- Targets:
  - classification: `target_passed`
  - regression: `target_accuracy`

## Primary API Inputs

The first iteration should collect data from these API areas:

- User rankings: seed players across skill bands
- User profile: player skill snapshot
- User recent scores: recent play outcomes, including fails
- Beatmap metadata: map difficulty and structure
- Beatmap attributes: optional mod-aware difficulty values

## Collection Strategy

Suggested flow:

1. Define ranking bands across the osu! performance ladder.
2. Sample a reproducible set of users from each band.
3. For each user, fetch the current user profile snapshot.
4. For each user, fetch recent scores with failures included.
5. For each user, optionally fetch best scores to improve positive-label coverage.
6. For each beatmap referenced by those scores, fetch beatmap metadata and cache it locally.
7. Flatten the result into one training row per score.

## Record Granularity Decision

Chosen row definition for V1:

- one row equals one observed user play attempt on one beatmap
- concretely: one score event for one `user_id` and one `beatmap_id`

This means the dataset is attempt-level, not an aggregated player-map summary.

### Why this was chosen

- It aligns naturally with the available recent score API data.
- It gives both MVP targets directly from the same score object.
- It keeps the first dataset flat, simple, and easy to reason about.
- It avoids premature aggregation logic that could hide useful pass/fail variance.

### Alternative considered

Alternative:

- one row per aggregated player-beatmap pair, for example combining multiple attempts into a single summary row

Why not for V1:

- It would require defining aggregation rules for repeated attempts.
- It would make target definitions less direct.
- It would add extra design complexity before the first pipeline exists.

## Row Definition

One row represents:

- one `user_id`
- on one `beatmap_id`
- for one observed score event
- with the user's current profile snapshot attached
- and the beatmap metadata attached

This is a snapshot-based dataset, not a fully historical reconstruction. That means player features reflect the current API profile at collection time, not necessarily the exact player profile at the moment the score was set.

## Target Compatibility With Row Definition

The selected row granularity is compatible with the two MVP targets:

- `target_passed` maps directly to the pass/fail outcome of that single observed attempt
- `target_accuracy` maps directly to the accuracy of that single observed attempt

This is one of the main reasons attempt-level rows are preferable for V1. Both targets are defined on the same score event, so no target aggregation or label reconstruction is required.

## Targets

| Column | Type | Required | Description | Source |
|---|---|---:|---|---|
| `target_passed` | boolean | yes | Whether the user passed the beatmap on this score. | user recent score |
| `target_accuracy` | float | yes | Observed score accuracy percentage for this play, stored as a 0-100 value. | user recent score |

## Core Schema

### Identity and context

| Column | Type | Required | Description | Source |
|---|---|---:|---|---|
| `row_id` | string | yes | Stable local row identifier, for example `{score_id}` or `{user_id}_{beatmap_id}_{created_at}`. | derived |
| `score_id` | integer | yes | Unique score identifier from the API. | user recent score |
| `user_id` | integer | yes | osu! user identifier. | user recent score |
| `beatmap_id` | integer | yes | Beatmap identifier. | user recent score |
| `beatmapset_id` | integer | yes | Beatmapset identifier. | beatmap |
| `ruleset` | string | yes | Ruleset name. V1 should always be `osu`. | collection config / API |
| `collected_at` | datetime | yes | Timestamp when this row was materialized from API responses during export. | exporter |
| `score_created_at` | datetime | yes | Timestamp when the score was created. | user recent score |

### Targets and observed score outcome

| Column | Type | Required | Description | Source |
|---|---|---:|---|---|
| `score_source` | string | yes | Source of the score row, such as `recent` or `best`. | collector |
| `target_passed` | boolean | yes | Pass/fail label for the score. | user recent score |
| `target_accuracy` | float | yes | Accuracy percentage for the observed play, stored as 0-100. | user recent score |
| `score_rank` | string | no | Score grade such as `A`, `S`, `F`. Useful for analysis, not required for inference. | user recent score |
| `mods_raw` | string | yes | Raw mod string, for example `HDHR` or empty. | user recent score |
| `observed_pp` | float | no | Performance points awarded for the observed score if present. | user recent score |
| `observed_max_combo` | integer | no | Max combo achieved on the observed play. | user recent score |
| `count_300` | integer | no | Number of 300 judgments. | user recent score |
| `count_100` | integer | no | Number of 100 judgments. | user recent score |
| `count_50` | integer | no | Number of 50 judgments. | user recent score |
| `count_miss` | integer | no | Number of misses. | user recent score |

### Sampling context

| Column | Type | Required | Description | Source |
|---|---|---:|---|---|
| `seed_band` | string | yes | Ranking band used when the user was sampled, for example `10001-20000`. | collector |
| `seed_user_rank` | integer | yes | Actual `global_rank` returned by the rankings endpoint at collection time. | rankings |

### Player snapshot features

| Column | Type | Required | Description | Source |
|---|---|---:|---|---|
| `user_pp` | float | yes | Current user PP at collection time. | user profile |
| `user_global_rank` | integer | no | Current global rank if available. | user profile |
| `user_country_rank` | integer | no | Current country rank if available. | user profile |
| `user_accuracy` | float | yes | Current profile accuracy percentage, stored as 0-100. | user profile |
| `user_play_count` | integer | yes | Current total play count. | user profile |
| `user_play_time_sec` | integer | no | Current total play time in seconds if available. | user profile |
| `user_total_hits` | integer | no | Current total hit count if available. | user profile |
| `user_maximum_combo` | integer | no | Current best maximum combo if available. | user profile |

### Beatmap features

| Column | Type | Required | Description | Source |
|---|---|---:|---|---|
| `beatmap_star_rating` | float | yes | Base star difficulty rating. | beatmap |
| `beatmap_bpm` | float | yes | Base BPM. | beatmap |
| `beatmap_ar` | float | yes | Approach rate. | beatmap |
| `beatmap_od` | float | yes | Overall difficulty. In the API this is represented by the beatmap `accuracy` field. | beatmap |
| `beatmap_cs` | float | yes | Circle size. | beatmap |
| `beatmap_hp` | float | no | HP drain rate. | beatmap |
| `beatmap_hit_length_sec` | integer | yes | Drain time or hit length in seconds. | beatmap |
| `beatmap_total_length_sec` | integer | yes | Total map length in seconds. | beatmap |
| `beatmap_count_circles` | integer | no | Number of circles. | beatmap |
| `beatmap_count_sliders` | integer | no | Number of sliders. | beatmap |
| `beatmap_count_spinners` | integer | no | Number of spinners. | beatmap |
| `beatmap_status` | string | no | Beatmap ranked status such as ranked or loved. | beatmap |
| `beatmap_passcount` | integer | yes | Historical total passes for the map. | beatmap |
| `beatmap_playcount` | integer | yes | Historical total plays for the map. | beatmap |

### Optional mod-aware difficulty features

| Column | Type | Required | Description | Source |
|---|---|---:|---|---|
| `modded_star_rating` | float | no | Star rating adjusted for the applied mod combination. | beatmap attributes |
| `modded_max_combo` | integer | no | Maximum combo adjusted for the applied mod combination. | beatmap attributes |

These fields are optional for the first dataset version. Store them only if the collection script actually calls the beatmap attributes endpoint for the row's mod combination.

## Required Columns for V1

The first training dataset should not be considered valid unless it contains at least these columns:

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
- `seed_band`
- `seed_user_rank`
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

## Recommended Storage Types

For a CSV or parquet starter dataset:

- IDs: integer
- timestamps: ISO 8601 string during raw export, converted to datetime during processing
- booleans: `true` / `false`
- percentages: store as 0-100 floats for readability
- mods: raw compact string such as `HDHR`, `DT`, or empty string

## Derived Features Deferred to Feature Engineering

These should not be required raw-source columns in the initial schema. They should be created later in the feature engineering layer:

- `star_gap`
- `bpm_gap`
- `od_gap`
- `ar_gap`
- `length_bucket`
- `has_hidden`
- `has_hardrock`
- `has_doubletime`
- normalized popularity features such as pass ratio

## Excluded from V1

To keep the first iteration tractable, do not require these in the initial dataset schema:

- multi-ruleset support
- full historical user snapshots
- social or profile decoration fields
- beatmap textual metadata such as artist, title, tags
- replay-level or event-level gameplay data
- FC probability labels
- PP prediction labels
- recommendation score labels

## Known Limitations

- Player features are snapshot features collected at data ingestion time, not guaranteed historical values from score time.
- Recent scores are suitable for an MVP but do not represent a complete play history.
- Best-score augmentation improves positive-label coverage, but it changes source mix and must be tracked through `score_source`.
- Fails are essential for the classifier, so the collection pipeline should explicitly request recent scores with failures included.
- Popularity fields like `beatmap_passcount` and `beatmap_playcount` may introduce bias. Keep them in the schema, but validate whether they help or hurt the first model.

## Granularity Tradeoffs

Benefits of attempt-level rows:

- direct labels for both classification and regression
- simpler collection pipeline
- easier debugging and data inspection
- closer alignment with the eventual `/predict` request, which represents one player-map scenario

Costs of attempt-level rows:

- repeated attempts from the same user can create correlation between rows
- current user profile features are only a snapshot proxy for historical state
- recent-score sampling may over-represent currently active players and recently played maps

Mitigation for V1:

- accept these tradeoffs for the first iteration
- document them clearly
- revisit grouping, deduplication, or time-aware splits after the first baseline works

## Review Decision for V1

Approved planning decisions:

- `osu` only
- recent user scores as the main source
- failures included
- keep `beatmap_passcount` and `beatmap_playcount` in the schema

## Starter Dataset Status

The repository should contain:

- a tracked local bootstrap dataset under `data/sample/`
- and an API-backed ranked collector for collecting real rows into `data/raw/`

This gives the project both:

- a zero-dependency local dataset for early pipeline work
- and a real collection path once OAuth credentials are available

Recommended raw storage format for large collections:

- JSONL for append-friendly raw snapshots
- one line per sampled user bundle
- one line per beatmap cache entry
- one line per sampled user manifest row
- a `state.json` progress file for resumable collection and live progress watching

Current collector limitation:

- this ranked collector depends on the public osu! rankings endpoint
- that endpoint currently exposes only the top `10000` users
- so band-based seeding for this collector must stay within `1-10000` unless a different seeding strategy is implemented

## Next Step

After the sample dataset exists, the next implementation item should be:

- run the ranked collector with real osu! OAuth credentials
- produce a reproducible band-sampled dataset under `data/raw/`
- inspect target balance, source mix, missingness, and repeated-user effects before model training
