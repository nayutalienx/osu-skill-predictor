# Engineered Difficulty-Gap Features

Project: `osu-skill-predictor`

## Purpose

This document defines the V1 "gap-style" engineered features that compare player comfort level to beatmap difficulty.

It answers three questions:

- which gap features are part of the first engineered-feature plan;
- how each feature should be computed or why it is deferred;
- which current MVP inputs are sufficient or insufficient to support those features.

## V1 Decision

For V1:

- `star_gap` is defined
- `bpm_gap` is deferred
- `od_gap` is deferred
- `ar_gap` is deferred

This is intentional.

The current MVP player feature set contains:

- `user_pp`
- `user_accuracy`
- `user_play_count`

That is enough to support one defensible player-vs-map difficulty proxy for stars, but it does not yet give a clean direct player-side comfort proxy for BPM, OD, or AR.

## Why Gap Features Matter

Raw beatmap difficulty alone is not enough.

The same map can be:

- easy for a strong player
- borderline for a mid-skill player
- impossible for a weak player

Gap features try to represent that interaction explicitly rather than forcing the model to learn it only from independent player and beatmap columns.

## Defined V1 Feature

### `star_gap`

Definition:

- `star_gap = beatmap_star_rating - player_star_comfort_estimate`

Interpretation:

- positive `star_gap`: the beatmap is harder than the player's estimated comfort level
- near-zero `star_gap`: the beatmap is close to the player's estimated comfort level
- negative `star_gap`: the beatmap is easier than the player's estimated comfort level

### How to estimate `player_star_comfort_estimate`

V1 should not hard-code a naive formula like "PP divided by constant equals stars."

Instead, define the player comfort estimate from the training data only.

Recommended approach:

1. use the training split only
2. bin players by `user_pp`
3. within each PP bin, compute an empirical central tendency of star difficulty for successful plays
4. use that empirical mapping as the player's star comfort estimate

Recommended central tendency:

- median `beatmap_star_rating` among passed attempts in that PP bin

Optional stricter version later:

- median `beatmap_star_rating` among passed attempts with `target_accuracy >= 95`

### Why this definition was chosen

Reasons:

- `user_pp` is the strongest available player skill summary in the MVP inputs
- `beatmap_star_rating` is the strongest available aggregate map difficulty summary
- a data-derived PP-to-comfort mapping is more defensible than an arbitrary hand-tuned conversion formula
- the mapping can be fit on the training split only, which keeps leakage manageable

### Leakage note for `star_gap`

The PP-to-star comfort mapping must be estimated using training data only.

Do not:

- compute the mapping on the full dataset before splitting

Correct behavior:

- split first
- fit the PP-to-star comfort mapping on train only
- apply the fitted mapping to train and test rows

## Deferred Features

### `bpm_gap`

Status:

- deferred for V1

Reason:

- the current MVP player feature set does not include a player BPM comfort proxy
- `user_pp`, `user_accuracy`, and `user_play_count` do not cleanly represent tempo-specific skill

What would be needed later:

- a derived player BPM comfort estimate from historical attempts, for example:
  - median BPM of passed attempts
  - high-percentile BPM of passed attempts
  - BPM estimate restricted to high-accuracy passes

Possible future definition:

- `bpm_gap = beatmap_bpm - player_bpm_comfort_estimate`

Why it is not in V1:

- that player-side estimate is not part of the current MVP raw feature contract
- introducing it now would require more historical aggregation design than the MVP needs

### `od_gap`

Status:

- deferred for V1

Reason:

- the current player snapshot does not contain a clean OD-specific comfort measure
- `user_accuracy` is a broad summary and should not be treated as a direct OD-scale metric

Possible future definition:

- `od_gap = beatmap_od - player_od_comfort_estimate`

Where `player_od_comfort_estimate` might later come from:

- OD levels of passed attempts
- OD levels of high-accuracy attempts
- a training-only empirical mapping from player summary features to comfortable OD

Why it is not in V1:

- there is no direct player-side OD proxy in the current MVP feature set
- forcing one now would create a weak and misleading feature

### `ar_gap`

Status:

- deferred for V1

Reason:

- the current player snapshot does not contain a clean reading-speed or AR-specific comfort measure
- `user_accuracy` and `user_pp` are too broad to serve as direct AR comfort features

Possible future definition:

- `ar_gap = beatmap_ar - player_ar_comfort_estimate`

Where `player_ar_comfort_estimate` might later come from:

- AR levels of passed attempts
- AR levels of strong-accuracy attempts
- a training-only empirical mapping learned from richer historical attempt summaries

Why it is not in V1:

- the MVP does not yet expose a trustworthy AR-specific player proxy

## Summary Table

| Feature | V1 status | Definition / reason |
|---|---|---|
| `star_gap` | defined | `beatmap_star_rating - player_star_comfort_estimate` |
| `bpm_gap` | deferred | no player BPM comfort proxy in current MVP inputs |
| `od_gap` | deferred | no clean player OD comfort proxy in current MVP inputs |
| `ar_gap` | deferred | no clean player AR comfort proxy in current MVP inputs |

## Relationship to Current MVP Feature Sets

This decision is consistent with the current docs:

- beatmap side already provides `beatmap_star_rating`, `beatmap_bpm`, `beatmap_od`, `beatmap_ar`
- player side currently requires only `user_pp`, `user_accuracy`, and `user_play_count`

That means:

- one star-based interaction feature is reasonable now
- BPM/OD/AR interaction features need more player-specific historical aggregation than the MVP currently defines

## V1 Practical Recommendation

For the first baseline:

- implement `star_gap` as the only required difficulty-gap feature
- fit the underlying PP-to-star comfort mapping on training data only
- explicitly defer `bpm_gap`, `od_gap`, and `ar_gap`
- revisit the deferred gap features only after richer player historical aggregates exist

This keeps the interaction-feature plan useful without inventing weak proxies that the current dataset does not support.
