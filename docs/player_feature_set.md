# MVP Player Feature Set

Project: `osu-skill-predictor`

## Purpose

This document defines the required player-side features for V1 predictions.

It answers three questions:

- which player summary attributes are part of the MVP feature set;
- what aggregation window or collection assumption each feature depends on;
- why each feature is included in the first tabular model.

## V1 Decision

The MVP player feature set should represent current skill using a compact profile snapshot.

Required core player features for V1:

- `user_pp`
- `user_accuracy`
- `user_play_count`

Recommended but optional player features for V1 analysis or later model expansion:

- `user_global_rank`
- `user_country_rank`
- `user_play_time_sec`
- `user_total_hits`
- `user_maximum_combo`

## Why This Feature Set Was Chosen

The project needs player features that are:

- available from the official osu! API v2 without replay parsing
- easy to attach to each score row
- interpretable in a classical tabular model
- good proxies for current player strength and experience

The MVP should avoid pretending it has perfect historical skill reconstruction.

So the first player feature set is intentionally:

- snapshot-based
- coarse
- reproducible
- limited to current profile summaries

## Collection Window and Assumption

All V1 player features are based on the current user profile at collection time.

This is the main aggregation assumption:

- the player snapshot is not necessarily the exact state when the score was originally set
- instead, it is the user profile returned by the API when the collector exported the row

Implications:

- these features are "current skill snapshot" proxies
- they are not true time-aligned historical features
- they may be slightly mismatched for older `best` scores or older recent scores

This assumption is acceptable for the MVP because:

- it keeps collection simple
- it matches the current API-backed collection design
- it is clearly documented and can be revisited later

## Core Feature Definitions

| Column | Source window / assumption | Expected dtype | Practical valid range | Rationale |
|---|---|---|---|---|
| `user_pp` | current profile snapshot at collection time | float | `>= 0` | Strong high-level proxy for overall player skill. |
| `user_accuracy` | current profile snapshot at collection time | float | `0` to `100` | Coarse proxy for timing consistency and precision. |
| `user_play_count` | cumulative profile total at collection time | integer | `>= 0` | Coarse proxy for player experience and account maturity. |

## Core Feature Rationales

### `user_pp`

- interpretation: broad skill summary
- why it matters: PP is the most compact and widely understood global skill proxy available in the API
- why it is required: without a skill-level anchor, beatmap difficulty features alone are not enough for pass/accuracy prediction

### `user_accuracy`

- interpretation: long-run profile accuracy percentage
- why it matters: it gives a coarse signal about how cleanly the player tends to hit objects overall
- why it is required: it is a natural player-side complement to beatmap `OD`, and it should help the regression target especially

### `user_play_count`

- interpretation: total lifetime play count
- why it matters: it is a simple experience proxy that distinguishes a similarly rated veteran from a newer player with less stable exposure
- why it is required: it adds player maturity context at almost no complexity cost

## Optional Player Features

These are useful but not required for the MVP contract.

| Column | Source window / assumption | Expected dtype | Practical valid range | Rationale |
|---|---|---|---|---|
| `user_global_rank` | current profile snapshot | integer | positive when present | Useful ranking context, but largely overlaps with PP. |
| `user_country_rank` | current profile snapshot | integer | positive when present | Helpful local-skill context, but not necessary for first baseline. |
| `user_play_time_sec` | cumulative profile total | integer | `>= 0` | Better experience proxy than play count in some cases, but optional. |
| `user_total_hits` | cumulative profile total | integer | `>= 0` | Coarse exposure volume proxy, but partly redundant with play count. |
| `user_maximum_combo` | current profile summary | integer | `>= 0` | Useful mechanical signal, but weaker and less central than PP. |

## Why These Optional Features Are Deferred

### `user_global_rank`

- useful for analysis
- partially redundant with `user_pp`
- may introduce additional rank-scale quirks without adding much beyond PP in V1

### `user_country_rank`

- useful for country-context inspection
- not essential for the prediction target itself
- can also reflect country-specific population effects that may not generalize cleanly

### `user_play_time_sec`

- plausible experience measure
- good candidate for later comparison
- not required for the first minimal player contract

### `user_total_hits`

- useful as a coarse volume statistic
- somewhat redundant with `user_play_count`
- better deferred until feature correlation is inspected

### `user_maximum_combo`

- potentially useful for map-stamina or execution capability context
- but less stable as an overall player summary than PP or profile accuracy

## Explicitly Excluded Player Features for MVP

The following player-side candidates are intentionally excluded from the required MVP set:

- join date or account age fields
- follower or social/profile decoration data
- badge counts
- medal counts
- avatar or profile presentation fields
- free-form textual profile metadata
- manually aggregated recent-score rolling windows
- replay-derived mechanics features
- session-level recent streak features

Reason for exclusion:

- not central to the MVP prediction task
- not cleanly available as simple, low-risk tabular inputs
- too noisy, too product-irrelevant, or too expensive to collect properly for V1

## Aggregation and Temporal Notes

### No rolling historical windows in V1

The MVP player feature set does not use:

- last-10 plays averages
- last-30 days activity windows
- recent pass-rate windows
- score-history-derived skill trends

Reason:

- these would require additional historical design choices
- they increase leakage and reproducibility complexity
- they are better introduced after the first baseline works

### Snapshot assumption must remain explicit

Every use of the V1 player feature set should remember:

- rows are score events
- player features are current profile snapshots
- therefore the player side is not historically exact

This is the defining assumption behind the MVP player feature set.

## Validation Rules for Core Player Features

Before training:

1. all core player columns must exist
2. all core player columns must be non-null
3. `user_pp >= 0`
4. `user_accuracy` must stay within `0` to `100`
5. `user_play_count >= 0`

Optional player fields, when present, should also satisfy:

- `user_global_rank > 0`
- `user_country_rank > 0`
- `user_play_time_sec >= 0`
- `user_total_hits >= 0`
- `user_maximum_combo >= 0`

## Relationship to Future Engineered Features

The MVP player feature set is the raw player-side input contract.

It does not yet include engineered interaction features such as:

- `star_gap`
- `bpm_gap`
- `od_gap`
- `ar_gap`

Those belong in a later feature-engineering step where player and beatmap features are combined.

## V1 Practical Recommendation

For the first baseline:

- require `user_pp`, `user_accuracy`, and `user_play_count`
- keep the player-side feature contract snapshot-based
- preserve optional player summary fields in cleaned data when available
- delay rolling historical or replay-derived player features until after the first baseline is evaluated

This keeps the player side of the MVP small, interpretable, and consistent with the current collector.
