from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit


DEFAULT_RANDOM_SEED = 42
SPLIT_STRATEGY_NAME = "grouped_user_shuffle_v1"

REQUIRED_COLUMNS = [
    "row_id",
    "score_id",
    "user_id",
    "beatmap_id",
    "beatmapset_id",
    "ruleset",
    "collected_at",
    "score_created_at",
    "score_source",
    "seed_country_code",
    "seed_country_rank",
    "seed_country_player_rank",
    "seed_global_rank",
    "target_passed",
    "target_accuracy",
    "mods_raw",
    "user_pp",
    "user_accuracy",
    "user_play_count",
    "beatmap_star_rating",
    "beatmap_bpm",
    "beatmap_ar",
    "beatmap_od",
    "beatmap_cs",
    "beatmap_hit_length_sec",
    "beatmap_total_length_sec",
    "beatmap_passcount",
    "beatmap_playcount",
]

NUMERIC_FEATURE_COLUMNS = [
    "user_pp",
    "user_accuracy",
    "user_play_count",
    "beatmap_star_rating",
    "beatmap_bpm",
    "beatmap_ar",
    "beatmap_od",
    "beatmap_cs",
    "beatmap_hit_length_sec",
    "beatmap_total_length_sec",
    "beatmap_passcount",
    "beatmap_playcount",
    "star_gap",
]

BOOLEAN_FEATURE_COLUMNS = [
    "has_hidden",
    "has_hardrock",
    "has_doubletime",
]

CATEGORICAL_FEATURE_COLUMNS = [
    "length_bucket",
]

ALL_FEATURE_COLUMNS = (
    NUMERIC_FEATURE_COLUMNS + BOOLEAN_FEATURE_COLUMNS + CATEGORICAL_FEATURE_COLUMNS
)

INT_COLUMNS = [
    "score_id",
    "user_id",
    "beatmap_id",
    "beatmapset_id",
    "seed_country_rank",
    "seed_country_player_rank",
    "seed_global_rank",
    "user_play_count",
    "beatmap_hit_length_sec",
    "beatmap_total_length_sec",
    "beatmap_passcount",
    "beatmap_playcount",
]

OPTIONAL_INT_COLUMNS = [
    "user_global_rank",
    "user_country_rank",
    "user_play_time_sec",
    "user_total_hits",
    "user_maximum_combo",
    "observed_max_combo",
    "count_300",
    "count_100",
    "count_50",
    "count_miss",
    "beatmap_count_circles",
    "beatmap_count_sliders",
    "beatmap_count_spinners",
]

FLOAT_COLUMNS = [
    "target_accuracy",
    "user_pp",
    "user_accuracy",
    "beatmap_star_rating",
    "beatmap_bpm",
    "beatmap_ar",
    "beatmap_od",
    "beatmap_cs",
]

OPTIONAL_FLOAT_COLUMNS = [
    "observed_pp",
    "beatmap_hp",
]

STRING_COLUMNS = [
    "row_id",
    "ruleset",
    "score_source",
    "seed_country_code",
    "score_rank",
    "mods_raw",
    "beatmap_status",
]

DATETIME_COLUMNS = [
    "collected_at",
    "score_created_at",
]


@dataclass
class ComfortMapping:
    edges: list[float]
    values: list[float]
    fallback_value: float


def find_latest_raw_csv(raw_root: str | Path = "data/raw") -> Path:
    root = Path(raw_root)
    candidates = []
    for run_dir in root.iterdir():
        if not run_dir.is_dir():
            continue
        csv_files = list(run_dir.glob("*.csv"))
        if not csv_files:
            continue
        latest_csv = max(csv_files, key=lambda path: path.stat().st_mtime)
        candidates.append((latest_csv.stat().st_mtime, latest_csv))
    if not candidates:
        raise FileNotFoundError(f"No raw dataset CSV found under {root}")
    return max(candidates, key=lambda item: item[0])[1]


def load_dataset_preview(csv_path: str | Path, n_rows: int = 5) -> pd.DataFrame:
    return pd.read_csv(csv_path, nrows=n_rows)


def ensure_required_columns(df: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")


def parse_boolean_series(series: pd.Series) -> pd.Series:
    normalized = series.astype("string").str.strip().str.lower()
    mapped = normalized.map({"true": True, "false": False})
    return mapped.astype("boolean")


def cast_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for column in STRING_COLUMNS:
        if column in result.columns:
            result[column] = result[column].astype("string")
    if "mods_raw" in result.columns:
        result["mods_raw"] = result["mods_raw"].fillna("").astype("string")
    result["target_passed"] = parse_boolean_series(result["target_passed"])
    for column in INT_COLUMNS + OPTIONAL_INT_COLUMNS:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce").astype("Int64")
    for column in FLOAT_COLUMNS + OPTIONAL_FLOAT_COLUMNS:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    for column in DATETIME_COLUMNS:
        result[column] = pd.to_datetime(result[column], errors="coerce", utc=True)
    return result


def clean_raw_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    ensure_required_columns(df)
    cleaned = cast_columns(df)
    report: dict[str, Any] = {
        "rows_loaded": int(len(cleaned)),
        "rows_dropped_missing_required": 0,
        "rows_dropped_ruleset": 0,
        "rows_dropped_score_source": 0,
        "rows_dropped_domain": 0,
        "rows_dropped_duplicate_row_id": 0,
    }

    required_non_null = [
        "row_id",
        "score_id",
        "user_id",
        "beatmap_id",
        "beatmapset_id",
        "ruleset",
        "collected_at",
        "score_created_at",
        "score_source",
        "seed_country_code",
        "seed_country_rank",
        "seed_country_player_rank",
        "seed_global_rank",
        "target_passed",
        "target_accuracy",
        "user_pp",
        "user_accuracy",
        "user_play_count",
        "beatmap_star_rating",
        "beatmap_bpm",
        "beatmap_ar",
        "beatmap_od",
        "beatmap_cs",
        "beatmap_hit_length_sec",
        "beatmap_total_length_sec",
        "beatmap_passcount",
        "beatmap_playcount",
    ]
    missing_required_mask = cleaned[required_non_null].isna().any(axis=1)
    report["rows_dropped_missing_required"] = int(missing_required_mask.sum())
    cleaned = cleaned.loc[~missing_required_mask].copy()

    ruleset_mask = cleaned["ruleset"].eq("osu")
    report["rows_dropped_ruleset"] = int((~ruleset_mask).sum())
    cleaned = cleaned.loc[ruleset_mask].copy()

    source_mask = cleaned["score_source"].isin(["recent", "best"])
    report["rows_dropped_score_source"] = int((~source_mask).sum())
    cleaned = cleaned.loc[source_mask].copy()

    domain_mask = (
        (cleaned["score_id"] >= 0)
        & (cleaned["user_id"] > 0)
        & (cleaned["beatmap_id"] > 0)
        & (cleaned["beatmapset_id"] > 0)
        & (cleaned["seed_country_rank"] > 0)
        & (cleaned["seed_country_player_rank"] > 0)
        & (cleaned["seed_global_rank"] > 0)
        & (cleaned["target_accuracy"].between(0, 100))
        & (cleaned["user_pp"] >= 0)
        & (cleaned["user_accuracy"].between(0, 100))
        & (cleaned["user_play_count"] >= 0)
        & (cleaned["beatmap_star_rating"] >= 0)
        & (cleaned["beatmap_bpm"] > 0)
        & (cleaned["beatmap_ar"].between(0, 12))
        & (cleaned["beatmap_od"].between(0, 12))
        & (cleaned["beatmap_cs"].between(0, 10))
        & (cleaned["beatmap_hit_length_sec"] >= 0)
        & (cleaned["beatmap_total_length_sec"] >= cleaned["beatmap_hit_length_sec"])
        & (cleaned["beatmap_passcount"] >= 0)
        & (cleaned["beatmap_playcount"] >= cleaned["beatmap_passcount"])
    )
    report["rows_dropped_domain"] = int((~domain_mask).sum())
    cleaned = cleaned.loc[domain_mask].copy()

    duplicate_mask = cleaned.duplicated(subset=["row_id"], keep="first")
    report["rows_dropped_duplicate_row_id"] = int(duplicate_mask.sum())
    cleaned = cleaned.loc[~duplicate_mask].copy()

    cleaned["target_passed"] = cleaned["target_passed"].astype(bool)
    cleaned["mods_raw"] = cleaned["mods_raw"].fillna("").astype(str)
    report["rows_kept"] = int(len(cleaned))
    return cleaned, report


def assign_length_bucket(series: pd.Series) -> pd.Series:
    conditions = [
        series < 60,
        (series >= 60) & (series < 150),
        series >= 150,
    ]
    values = ["short", "medium", "long"]
    return pd.Series(np.select(conditions, values, default="medium"), index=series.index).astype("string")


def contains_mod(series: pd.Series, token: str) -> pd.Series:
    return series.fillna("").astype(str).str.contains(token, regex=False)


def fit_star_comfort_mapping(train_df: pd.DataFrame, q: int = 20) -> ComfortMapping:
    passed = train_df.loc[train_df["target_passed"]]
    fallback_value = float(passed["beatmap_star_rating"].median()) if not passed.empty else float(train_df["beatmap_star_rating"].median())
    user_pp_values = train_df["user_pp"].to_numpy(dtype=float)
    if len(user_pp_values) == 0:
        return ComfortMapping(edges=[0.0, 1.0], values=[fallback_value], fallback_value=fallback_value)

    raw_edges = np.quantile(user_pp_values, np.linspace(0.0, 1.0, min(q, len(train_df)) + 1))
    edges = np.unique(raw_edges)
    if len(edges) < 2:
        single_edge = float(edges[0]) if len(edges) == 1 else 0.0
        return ComfortMapping(
            edges=[single_edge, single_edge + 1.0],
            values=[fallback_value],
            fallback_value=fallback_value,
        )

    bin_count = len(edges) - 1
    assigned_bins = pd.cut(
        train_df["user_pp"],
        bins=edges,
        include_lowest=True,
        labels=False,
        duplicates="drop",
    )
    train_bins = pd.Series(assigned_bins, index=train_df.index, dtype="Int64")
    passed_bins = train_bins.loc[passed.index]
    bin_medians = passed.groupby(passed_bins)["beatmap_star_rating"].median()

    values: list[float] = []
    last_value = fallback_value
    for bin_index in range(bin_count):
        value = bin_medians.get(bin_index)
        if pd.isna(value):
            value = last_value
        else:
            value = float(value)
        values.append(float(value))
        last_value = float(value)

    if all(value == fallback_value for value in values):
        values = [fallback_value for _ in range(bin_count)]

    return ComfortMapping(
        edges=[float(edge) for edge in edges.tolist()],
        values=values,
        fallback_value=fallback_value,
    )


def apply_star_comfort_mapping(user_pp: pd.Series, mapping: ComfortMapping) -> pd.Series:
    values = user_pp.to_numpy(dtype=float)
    edges = np.asarray(mapping.edges, dtype=float)
    bin_indices = np.searchsorted(edges[1:-1], values, side="right")
    mapped = np.array([mapping.values[min(max(int(index), 0), len(mapping.values) - 1)] for index in bin_indices], dtype=float)
    mapped[np.isnan(values)] = mapping.fallback_value
    return pd.Series(mapped, index=user_pp.index, name="player_star_comfort_estimate")


def engineer_features(df: pd.DataFrame, mapping: ComfortMapping) -> pd.DataFrame:
    engineered = df.copy()
    engineered["length_bucket"] = assign_length_bucket(engineered["beatmap_hit_length_sec"])
    engineered["has_hidden"] = contains_mod(engineered["mods_raw"], "HD").astype(int)
    engineered["has_hardrock"] = contains_mod(engineered["mods_raw"], "HR").astype(int)
    engineered["has_doubletime"] = (
        contains_mod(engineered["mods_raw"], "DT") | contains_mod(engineered["mods_raw"], "NC")
    ).astype(int)
    engineered["player_star_comfort_estimate"] = apply_star_comfort_mapping(engineered["user_pp"], mapping)
    engineered["star_gap"] = engineered["beatmap_star_rating"] - engineered["player_star_comfort_estimate"]
    return engineered


def build_split_assignment(
    df: pd.DataFrame,
    random_seed: int = DEFAULT_RANDOM_SEED,
    test_size: float = 0.2,
) -> pd.DataFrame:
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_seed)
    train_indices, test_indices = next(splitter.split(df, groups=df["user_id"]))
    split_names = pd.Series(index=df.index, dtype="string")
    split_names.iloc[train_indices] = "train"
    split_names.iloc[test_indices] = "test"
    return pd.DataFrame(
        {
            "row_id": df["row_id"].astype(str),
            "user_id": df["user_id"].astype("int64"),
            "split_name": split_names.astype("string"),
            "split_random_seed": random_seed,
            "split_strategy": SPLIT_STRATEGY_NAME,
        }
    )
