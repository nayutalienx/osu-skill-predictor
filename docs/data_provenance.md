# Data Source and Provenance

Project: `osu-skill-predictor`

## Purpose

This note records where the current dataset artifacts came from, which assumptions were made during collection, and which parts of the repository are synthetic or manually curated.

It covers both:

- the tracked starter sample under `data/sample/`
- the API-backed collection flow under `data/raw/`

## Current Data Artifacts

### Starter sample

Tracked local bootstrap artifact:

- `data/sample/osu_ranked_attempts_sample_v1.csv`

Purpose:

- provide a small schema-compatible file that loads locally without external services
- exercise feature engineering, validation, and training code before relying on a live export

Status:

- manually curated
- synthetic as a repository bootstrap asset
- not intended to represent a statistically valid training dataset

### Full API-backed collections

Current live collection flow writes run directories under:

- `data/raw/`

A typical run directory contains:

- `config.json`
- `state.json`
- `export_metadata.json`
- `collector.stdout.log`
- `collector.stderr.log`
- `raw/sampled_users.jsonl`
- `raw/ranking_pages.jsonl`
- `raw/user_snapshots.jsonl`
- `raw/beatmaps.jsonl`
- flattened CSV output
- `profiling_summary.md`

These runs are intended to be the real training-data source for the project.

## Primary Data Sources

The current collector uses the official osu! API v2.

Main source areas:

- country rankings endpoint
  - used to choose the top countries for seeding
- country-local player rankings endpoint
  - used to sample players from each selected country's leaderboard
- user profile endpoint
  - used for player snapshot features at collection time
- user score endpoints
  - recent scores with `include_fails=1`
  - best scores for positive-label coverage
- beatmap metadata endpoint
  - used to enrich score rows with beatmap difficulty and structure

Authentication:

- OAuth client credentials flow
- local credentials are read from `.env.local` or `.env`

## Collection Assumptions

The current collection pipeline makes these explicit assumptions:

- ruleset is `osu` only
- one row represents one observed score event on one beatmap by one user
- recent scores are fetched with failures included
- best scores are also fetched to improve positive-label coverage
- user features are snapshot features collected at export time, not guaranteed historical values from the exact score timestamp
- country-seeded sampling is used instead of global rank-band sampling
- each selected country contributes the same number of sampled users in the current default configuration
- local country ranks are sampled from the top `10000` players of each selected country because that is the effective public ranking window currently exposed by the endpoint

## Manual and Derived Transformations

The collector performs these transformations before producing the flat CSV:

- samples countries from the country rankings endpoint
- samples country-local player ranks using a deterministic random seed
- stores both local country rank and global rank at sample time
- merges `recent` and `best` score sources into one flat row stream
- deduplicates overlapping score records when the same score appears in both sources
- normalizes mod lists into a compact `mods_raw` string
- converts accuracy values to a 0-100 scale for readability
- flattens nested API payloads into one row per score event
- joins beatmap metadata onto score rows using `beatmap_id`
- writes intermediate raw API snapshots in JSONL form
- writes a flattened CSV and profiling summary for downstream work

## Manual or Synthetic Elements

The repository currently contains these non-live elements:

- `data/sample/osu_ranked_attempts_sample_v1.csv`
  - hand-authored bootstrap data
  - schema-compatible, but synthetic/manual
- notebook execution output in `notebooks/`
  - may include captured progress or run metadata from interactive use

These elements are useful for development convenience, but they should not be confused with the main API-backed dataset.

## Limitations of the Starter Dataset

The starter sample has important limitations:

- it is very small
- it is manually curated
- it does not reflect the real distribution of players, maps, mods, or failures
- it is not appropriate for serious training or evaluation
- it is only intended to validate schema shape, file loading, and local pipeline wiring

Because of those limitations, model conclusions must not be drawn from the starter sample.

## Limitations of the API-Backed Dataset

The current live collection also has important limitations:

- it is not a full historical play log
- user profile features are snapshot values at collection time
- country-balanced seeding is a sampling choice, not a natural representation of the full player population
- recent and best score mixes can bias target distributions
- pass/fail balance may be highly skewed
- beatmap popularity fields may introduce popularity bias into models
- the collector depends on public country ranking coverage and therefore cannot sample beyond the exposed country-local top `10000` window without a different strategy

## Recommended Interpretation

For repository work:

- use `data/sample/` to test local loading and code paths
- use `data/raw/` run directories as the real experimental dataset source
- treat `profiling_summary.md` and `export_metadata.json` as the first reference for understanding a collected run

For modeling:

- do not assume the starter sample reflects production behavior
- inspect source mix, pass/fail balance, missingness, and country effects before training baselines
- document any additional preprocessing or filtering done after raw collection
