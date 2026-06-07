# Assumptions And Limitations

Project: `osu-skill-predictor`

## Purpose

This document captures the main boundaries of the MVP so the project remains honest and easy to review.

## Data Assumptions

- the project uses osu! API-derived tabular summaries rather than replay-level gameplay data
- player features are current or collection-time snapshots, not exact historical player state at score time
- one dataset row represents one observed player attempt on one beatmap
- sampling is country-seeded and not a complete census of all osu! players or all attempts
- only `osu` standard mode is in scope for the current dataset and models

## Modeling Assumptions

- player-vs-map suitability can be approximated with compact tabular features
- a shared preprocessing pipeline plus classical models is sufficient for the MVP
- grouped user-based splitting is a reasonable first defense against the biggest leakage path
- `star_gap` is a useful interaction feature even though the comfort estimate is indirect
- recommendation text can remain rule-based on top of model outputs in the MVP

## Data Limitations

- the dataset is sampled, not exhaustively historical
- repeated attempts, map overlap, and collection bias can still affect evaluation
- pass/fail and accuracy outcomes may reflect collection-time selection effects
- some map popularity features such as `passcount` and `playcount` may inject popularity bias

## Model Limitations

- predictions are probabilistic estimates, not guarantees
- the classifier is still easier to score well on this dataset than a truly adversarial fail-detection setting
- the regressor is only as good as the compact summary features allow
- no time-aware modeling is used
- no sequence modeling, replay analysis, or richer temporal player history is included

## API Limitations

- the API requires the local serialized model artifacts to exist
- the service does not retrain models automatically
- the service returns a single prediction response and does not currently support batch prediction
- the service does not include authentication, persistence, or deployment infrastructure
- internal failures are surfaced as short local debugging messages rather than production-grade structured logging

## Scope Limitations

Out of scope for the current MVP:

- deep learning
- online retraining
- replay or event-stream ingestion
- full recommendation-system behavior
- production deployment and scaling
- cross-mode coverage for taiko, catch, or mania

## Practical Interpretation

This project should be evaluated as:

- a production-shaped local ML portfolio project
- a reproducible baseline prediction service
- a clear example of data collection, feature engineering, model comparison, serialization, and API serving

It should not be evaluated as:

- a final competitive osu! skill platform
- a leaderboard-grade ranking system
- a comprehensive gameplay understanding model
