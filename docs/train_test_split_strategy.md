# Train/Test Split Strategy

Project: `osu-skill-predictor`

## Purpose

This document defines the first train/test split strategy for the V1 dataset.

The goal is to choose a split that is:

- simple enough to implement quickly;
- reproducible across runs;
- appropriate for the current dataset size and attempt-level row granularity;
- conservative about leakage.

## V1 Decision

Use a grouped random split by `user_id`.

Chosen approach:

- split unit: unique `user_id`
- train ratio: `80%`
- test ratio: `20%`
- random seed: fixed global split seed `42`

This means:

- a player appears in exactly one side of the split
- all attempts from a given user stay together
- the split is random at the user level, not at the row level

## Why This Strategy Was Chosen

The current dataset is attempt-level and contains repeated rows per player.

If rows were split independently:

- the same player could appear in both train and test
- the model could learn player-specific signals from the training side
- test performance would likely be too optimistic

The current full dataset size is large enough to support a user-level holdout:

- about `184k` rows
- about `10k` unique users

That is enough for a simple grouped split without immediately starving the train or test sets.

## Exact Split Rule

### Canonical V1 holdout

Use:

- `80%` of unique users for training
- `20%` of unique users for testing

Implementation expectation:

- shuffle unique `user_id` values with seed `42`
- assign the first `80%` of users to train
- assign the remaining `20%` to test

Equivalent library options:

- `GroupShuffleSplit` with `test_size=0.2` and `random_state=42`
- or deterministic hashing of `user_id` plus seed, if a library-free implementation is preferred later

### Validation split note

This backlog item only fixes the train/test strategy.

If a validation set is later needed for model comparison or threshold tuning, carve it only from the training users, not from the full dataset, and keep the same grouping rule by `user_id`.

Recommended future extension:

- train users: `72%`
- validation users: `8%`
- test users: `20%`

That can be achieved as:

1. grouped `80/20` train/test split
2. grouped `90/10` split inside the training users for train/validation

## Random Seed Strategy

The V1 split must be reproducible.

Canonical split seed:

- `42`

Rules:

- use the same seed for every baseline comparison unless there is an explicit experiment to study split sensitivity
- record the split seed in:
  - training configuration
  - experiment metadata
  - any saved metrics or model card notes
- do not let each notebook run pick a fresh random seed implicitly

Practical recommendation:

- define one named constant such as `SPLIT_RANDOM_SEED = 42`
- keep it near other training configuration values

## Leakage Risks and Mitigations

### Same-user leakage

Risk:

- the same player appears in both train and test through different attempts

Why it matters:

- user snapshot fields like `user_pp`, `user_accuracy`, and `user_play_count` are strong identity-adjacent signals
- test metrics would overstate generalization if the model sees the same user on both sides

Mitigation:

- split by `user_id`, not by row

### Same-score leakage

Risk:

- exact duplicate score rows or overlapping `recent` and `best` entries leak across splits

Mitigation:

- deduplicate before splitting
- use `row_id` and `score_id` validation checks before training

### Same-beatmap leakage

Risk:

- the same beatmap appears in both train and test across different users

Why it matters:

- the model can partially memorize beatmap difficulty patterns

V1 decision:

- accept this risk for the initial baseline

Reason:

- the product goal is to predict a player-beatmap outcome using known beatmap features
- seeing the same beatmap across different users is not automatically invalid for the intended use case
- holding out all beatmaps would answer a stricter question than the MVP currently needs

Future stricter evaluation option:

- add a second benchmark with beatmap-grouped or user-and-beatmap-aware splitting after the first baseline exists

### Preprocessing leakage

Risk:

- imputers, scalers, encoders, or feature selection are fit on the full dataset before the split

Mitigation:

- split first
- fit all preprocessing only on the training partition
- apply the fitted preprocessing objects to validation and test

### Temporal leakage

Risk:

- future attempts and older attempts from the same player are mixed when the split is random

V1 decision:

- accept random grouped splitting for the first iteration

Reason:

- the raw dataset is already snapshot-based rather than a strict historical reconstruction
- a clean time-aware evaluation can be added later, but it is not the simplest first baseline

## Dataset Checks After Splitting

After the split is created, inspect:

1. train row count and test row count
2. train unique-user count and test unique-user count
3. pass-rate difference between train and test
4. source mix difference between `recent` and `best`
5. country coverage difference between train and test
6. major beatmap-feature range differences between train and test

These checks are not meant to force exact equality, but they should catch obviously broken splits.

## Non-Goals for V1

This first split strategy does not attempt to:

- enforce exact class stratification at the row level
- balance every country perfectly across train and test
- hold out unseen beatmaps
- simulate production-time chronology exactly

Those are valid future experiments, but they are intentionally out of scope for the first reproducible baseline.

## V1 Practical Recommendation

For the first baseline:

- deduplicate the cleaned dataset
- create one grouped `80/20` split by `user_id`
- use seed `42`
- keep that split fixed across early model comparisons
- record the split seed and user counts in experiment outputs

This gives the project a straightforward and defensible starting point without pretending the evaluation is stricter than it really is.
