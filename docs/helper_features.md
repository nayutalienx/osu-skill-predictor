# Bucketed and Binary Helper Features

Project: `osu-skill-predictor`

## Purpose

This document defines a small set of simple, interpretable helper features for the V1 baseline.

The goal is to add a few low-complexity engineered columns that:

- are easy to explain
- are easy to implement
- are compatible with the current raw schema
- may improve baseline performance without introducing heavy preprocessing

## V1 Decision

Define these helper features:

- `length_bucket`
- `has_hidden`
- `has_hardrock`
- `has_doubletime`

These features are derived from:

- `beatmap_hit_length_sec`
- `mods_raw`

## `length_bucket`

### Source field

- `beatmap_hit_length_sec`

### Why hit length is used

Use active drain time rather than total listed length because hit length better reflects how long the player is actually under gameplay pressure.

### Definition

`length_bucket` is a categorical feature derived from `beatmap_hit_length_sec` using these V1 buckets:

- `short` if `beatmap_hit_length_sec < 60`
- `medium` if `60 <= beatmap_hit_length_sec < 150`
- `long` if `beatmap_hit_length_sec >= 150`

### Rationale

- `short` maps often reward burst execution and may be easier to retry aggressively
- `medium` maps cover the common baseline play-length range
- `long` maps introduce more sustained stamina, concentration, and failure risk

### Missing-value rule

- if `beatmap_hit_length_sec` is missing, the row should already be invalid under the current core-feature policy
- therefore `length_bucket` should never need a separate missing bucket in V1

## `has_hidden`

### Source field

- `mods_raw`

### Definition

`has_hidden` is a boolean feature:

- `true` if canonical `mods_raw` contains token `HD`
- `false` otherwise

Examples:

- `""` -> `false`
- `HD` -> `true`
- `HDHR` -> `true`
- `HDDT` -> `true`

### Rationale

Hidden changes reading behavior and can affect both pass probability and accuracy. It is common enough to merit an explicit helper flag.

## `has_hardrock`

### Source field

- `mods_raw`

### Definition

`has_hardrock` is a boolean feature:

- `true` if canonical `mods_raw` contains token `HR`
- `false` otherwise

Examples:

- `""` -> `false`
- `HR` -> `true`
- `HDHR` -> `true`
- `EZ` -> `false`

### Rationale

HardRock directly changes map difficulty characteristics and is a strong interpretable modifier of expected challenge.

## `has_doubletime`

### Source field

- `mods_raw`

### Definition

`has_doubletime` is a boolean feature:

- `true` if canonical `mods_raw` contains token `DT` or token `NC`
- `false` otherwise

Examples:

- `DT` -> `true`
- `NC` -> `true`
- `HDDT` -> `true`
- `HDNC` -> `true`
- `HT` -> `false`

### Rationale

Nightcore is effectively a DoubleTime-family speed modifier for the purposes of baseline feature engineering, so both should map to the same helper signal.

## Parsing Assumptions

These helper features assume:

- `mods_raw` already follows the canonical representation defined in [mod_parsing_rules.md](mod_parsing_rules.md)
- canonical values are uppercase
- no-mod is represented by `""`
- recognized combined strings are already normalized

If `mods_raw` contains unknown or unsupported content:

- derive the helper flags only from recognized safe tokens
- do not reject the row solely because a helper flag cannot fully interpret every token

## Output Types

Recommended output types:

- `length_bucket`: categorical string
- `has_hidden`: boolean
- `has_hardrock`: boolean
- `has_doubletime`: boolean

## Why These Features Were Chosen

These features are intentionally simple:

- `length_bucket` adds a coarse duration/stamina signal without needing scaling-heavy numeric transformations
- `has_hidden`, `has_hardrock`, and `has_doubletime` capture three common mod families that meaningfully affect difficulty and interpretation

They are also easy to inspect manually, which is useful for the first baseline.

## Explicit Non-Goals for V1

Do not require these helper features yet:

- `has_flashlight`
- `has_easy`
- `has_half_time`
- object-count buckets
- popularity buckets
- multi-mod interaction flags beyond the three booleans above

Reason:

- the first helper-feature layer should stay minimal and interpretable

## V1 Practical Recommendation

For the first baseline:

- add `length_bucket`
- add `has_hidden`
- add `has_hardrock`
- add `has_doubletime`

Keep them as lightweight derived features on top of the cleaned dataset before model training.
