# MVP Beatmap Feature Set

Project: `osu-skill-predictor`

## Purpose

This document defines the required beatmap-side features for V1 predictions.

It answers three questions:

- which beatmap attributes are part of the MVP input contract;
- what units and practical value ranges those attributes use;
- which candidate beatmap features are intentionally excluded or deferred.

## V1 Decision

The MVP beatmap feature set should stay small and difficulty-focused.

Required core beatmap features for V1:

- `beatmap_star_rating`
- `beatmap_bpm`
- `beatmap_ar`
- `beatmap_od`
- `beatmap_cs`
- `beatmap_hit_length_sec`
- `beatmap_total_length_sec`
- `beatmap_passcount`
- `beatmap_playcount`

These are the beatmap attributes that must be present for a row to be considered valid for V1 training and inference-oriented feature preparation.

## Why These Features Were Chosen

The V1 goal is to predict:

- whether a player can pass a beatmap;
- the expected accuracy of that attempt.

For that goal, the first beatmap feature set should capture:

- overall map difficulty
- timing pressure
- reading pressure
- precision pressure
- object size pressure
- map duration
- coarse popularity and survivorship context

The selected core features cover those needs without relying on replay data, text metadata, or heavy feature engineering.

## Core Feature Definitions

| Column | Unit | Expected dtype | Practical valid range | Purpose |
|---|---|---|---|---|
| `beatmap_star_rating` | stars | float | `>= 0`, commonly about `0` to `12+` | Overall aggregate difficulty proxy. |
| `beatmap_bpm` | beats per minute | float | `> 0`, commonly about `60` to `300+` | Timing speed and rhythm pressure proxy. |
| `beatmap_ar` | AR points | float | commonly `0` to `12` | Reading difficulty proxy through object approach timing. |
| `beatmap_od` | OD points | float | commonly `0` to `12` | Hit-window strictness proxy for accuracy pressure. |
| `beatmap_cs` | CS points | float | commonly `0` to `10` | Object size / spatial precision proxy. |
| `beatmap_hit_length_sec` | seconds | integer | `>= 0` | Active drain-time length of playable section. |
| `beatmap_total_length_sec` | seconds | integer | `>= 0`, typically `>= beatmap_hit_length_sec` | Full map length including non-drain sections. |
| `beatmap_passcount` | count of passes | integer | `>= 0` | Coarse popularity and historical survivorship signal. |
| `beatmap_playcount` | count of plays | integer | `>= 0`, typically `>= beatmap_passcount` | Coarse popularity / exposure signal. |

## Units and Interpretation Notes

### `beatmap_star_rating`

- unit: stars
- interpretation: a compact overall difficulty summary
- note: useful as the main beatmap difficulty feature in V1, but it should not be treated as a complete explanation of map difficulty by itself

### `beatmap_bpm`

- unit: beats per minute
- interpretation: tempo pressure
- note: BPM does not fully capture burst patterns, density, or rhythm complexity, but it is still a strong baseline timing feature

### `beatmap_ar`

- unit: AR scale points
- interpretation: reading pressure through approach timing
- practical range for validation: `0` to `12`

### `beatmap_od`

- unit: OD scale points
- interpretation: timing strictness / hit-window pressure
- data-source note: in the osu! beatmap payload this is mapped from the API field named `accuracy`
- practical range for validation: `0` to `12`

### `beatmap_cs`

- unit: CS scale points
- interpretation: object-size precision pressure
- practical range for validation: `0` to `10`

### `beatmap_hit_length_sec`

- unit: seconds
- interpretation: active gameplay duration
- note: this is preferable to total length when reasoning about sustained execution demand

### `beatmap_total_length_sec`

- unit: seconds
- interpretation: full listed map duration
- note: useful alongside hit length to distinguish dead time from active difficulty time

### `beatmap_passcount` and `beatmap_playcount`

- unit: absolute count
- interpretation: historical aggregate map exposure and success context
- note: these may help the first model, but they may also introduce popularity bias; they are kept in the MVP feature set and should be monitored during evaluation

## Validation Rules for the Core Beatmap Set

Before training:

1. all core beatmap columns must exist
2. all core beatmap columns must be non-null
3. `beatmap_star_rating >= 0`
4. `beatmap_bpm > 0`
5. `beatmap_ar` should stay within a practical validation range of `0` to `12`
6. `beatmap_od` should stay within a practical validation range of `0` to `12`
7. `beatmap_cs` should stay within a practical validation range of `0` to `10`
8. `beatmap_hit_length_sec >= 0`
9. `beatmap_total_length_sec >= 0`
10. `beatmap_total_length_sec >= beatmap_hit_length_sec`
11. `beatmap_passcount >= 0`
12. `beatmap_playcount >= 0`
13. `beatmap_playcount >= beatmap_passcount`

## Excluded or Deferred Candidate Features

These beatmap-related features were considered but are not part of the required MVP set.

### Deferred but potentially useful

- `beatmap_hp`
  - useful for survival difficulty, but not required for the first minimal contract
- `beatmap_count_circles`
  - useful for map structure, but not core enough for V1
- `beatmap_count_sliders`
  - useful for map structure, but deferred
- `beatmap_count_spinners`
  - useful for map structure, but deferred
- `beatmap_status`
  - may matter for distribution analysis, but not required for baseline prediction
- `modded_star_rating`
  - useful once mod-aware beatmap attributes are collected consistently
- `modded_max_combo`
  - useful later, but currently optional and coverage-dependent

### Explicitly excluded from the MVP beatmap contract

- beatmap title
- artist
- difficulty version name
- mapper username
- beatmapset tags
- textual metadata of any kind
- cover image or media assets
- leaderboard position data
- replay-level signals
- hand-crafted rhythm-pattern annotations

Reason for exclusion:

- these features either introduce unnecessary complexity, high-cardinality text handling, weak direct value for the first baseline, or dependence on data we do not currently collect cleanly

## Feature Set Boundaries

The MVP beatmap feature set is intended to describe the map itself, not the player-map interaction.

So this document does not include:

- player snapshot features
- mod-derived binary flags like `has_hidden`
- engineered gap features like `star_gap`, `ar_gap`, or `od_gap`

Those belong in later feature engineering or in separate player-feature planning docs.

## V1 Practical Recommendation

For the first baseline:

- require the nine core beatmap features listed above
- validate their units and practical ranges
- keep deferred beatmap fields available in raw or cleaned data when present
- do not expand the required beatmap contract until the first baseline is trained and inspected

This keeps the beatmap side of the MVP simple, defensible, and compatible with the current collector.
