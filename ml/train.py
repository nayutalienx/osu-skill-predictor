from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from .evaluate import evaluate_classifier, evaluate_regressor, get_model_feature_importance
from .features import (
    ALL_FEATURE_COLUMNS,
    DEFAULT_RANDOM_SEED,
    SPLIT_STRATEGY_NAME,
    build_split_assignment,
    clean_raw_dataset,
    engineer_features,
    find_latest_raw_csv,
    fit_star_comfort_mapping,
)
from .pipeline import build_classifier_pipeline, build_regressor_pipeline


ARTIFACT_VERSION = "v1"


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def selected_estimator_params(estimator: Any) -> dict[str, Any]:
    params = estimator.get_params(deep=False)
    selected_keys = [
        "n_estimators",
        "max_depth",
        "min_samples_leaf",
        "class_weight",
        "random_state",
    ]
    return {key: params[key] for key in selected_keys if key in params}


def build_run_paths(
    raw_csv_path: Path,
    processed_root: Path,
    models_root: Path,
) -> tuple[Path, Path]:
    raw_run_name = raw_csv_path.parent.name
    return processed_root / raw_run_name, models_root


def run_baseline_training(
    raw_csv_path: str | Path | None = None,
    processed_root: str | Path = "data/processed",
    models_root: str | Path = "models",
    random_seed: int = DEFAULT_RANDOM_SEED,
) -> dict[str, Any]:
    raw_csv = Path(raw_csv_path) if raw_csv_path else find_latest_raw_csv()
    processed_dir, models_dir = build_run_paths(raw_csv, Path(processed_root), Path(models_root))
    processed_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    raw_df = pd.read_csv(raw_csv)
    cleaned_df, cleaning_report = clean_raw_dataset(raw_df)
    split_assignment = build_split_assignment(cleaned_df, random_seed=random_seed)
    train_mask = split_assignment["split_name"].eq("train").to_numpy()
    comfort_mapping = fit_star_comfort_mapping(cleaned_df.iloc[train_mask].copy())
    training_df = engineer_features(cleaned_df, comfort_mapping)

    feature_frame = training_df[ALL_FEATURE_COLUMNS].copy()
    classifier_target = training_df["target_passed"].astype(int)
    regressor_target = training_df["target_accuracy"].astype(float)

    X_train = feature_frame.loc[train_mask]
    X_test = feature_frame.loc[~train_mask]
    y_class_train = classifier_target.loc[train_mask]
    y_class_test = classifier_target.loc[~train_mask]
    y_reg_train = regressor_target.loc[train_mask]
    y_reg_test = regressor_target.loc[~train_mask]

    classifier = build_classifier_pipeline(random_seed=random_seed)
    regressor = build_regressor_pipeline(random_seed=random_seed)
    classifier.fit(X_train, y_class_train)
    regressor.fit(X_train, y_reg_train)

    classifier_metrics = evaluate_classifier(classifier, X_test, y_class_test)
    regressor_metrics = evaluate_regressor(regressor, X_test, y_reg_test)

    cleaned_path = processed_dir / "cleaned_dataset.parquet"
    training_path = processed_dir / "training_dataset.parquet"
    split_path = processed_dir / "split_assignment.parquet"
    metadata_path = processed_dir / "dataset_metadata.json"
    cleaned_df.to_parquet(cleaned_path, index=False)
    training_df.to_parquet(training_path, index=False)
    split_assignment.to_parquet(split_path, index=False)

    dataset_metadata = {
        "artifact_version": ARTIFACT_VERSION,
        "processed_at": iso_now(),
        "source_raw_csv": raw_csv.as_posix(),
        "row_counts": {
            "loaded": int(len(raw_df)),
            "cleaned": int(len(cleaned_df)),
            "train": int(train_mask.sum()),
            "test": int((~train_mask).sum()),
        },
        "unique_counts": {
            "users": int(cleaned_df["user_id"].nunique()),
            "beatmaps": int(cleaned_df["beatmap_id"].nunique()),
        },
        "split": {
            "strategy": SPLIT_STRATEGY_NAME,
            "random_seed": random_seed,
            "test_ratio": 0.2,
        },
        "feature_columns": ALL_FEATURE_COLUMNS,
        "target_columns": ["target_passed", "target_accuracy"],
        "cleaning_report": cleaning_report,
    }
    write_json(metadata_path, dataset_metadata)

    classifier_path = models_dir / "pass_model.joblib"
    regressor_path = models_dir / "accuracy_model.joblib"
    model_metadata_path = models_dir / "model_metadata.json"
    joblib.dump(classifier, classifier_path)
    joblib.dump(regressor, regressor_path)

    model_metadata = {
        "artifact_version": ARTIFACT_VERSION,
        "trained_at": iso_now(),
        "source_raw_csv": raw_csv.as_posix(),
        "source_processed_dir": processed_dir.as_posix(),
        "split_strategy": SPLIT_STRATEGY_NAME,
        "split_random_seed": random_seed,
        "feature_columns": ALL_FEATURE_COLUMNS,
        "artifacts": {
            "pass_model": classifier_path.as_posix(),
            "accuracy_model": regressor_path.as_posix(),
        },
        "classifier": {
            "estimator": "RandomForestClassifier",
            "estimator_params": selected_estimator_params(classifier.named_steps["model"]),
            "target": "target_passed",
            "primary_metric": {
                "name": "pr_auc",
                "value": classifier_metrics["pr_auc"],
            },
            "metrics": classifier_metrics,
        },
        "regressor": {
            "estimator": "RandomForestRegressor",
            "estimator_params": selected_estimator_params(regressor.named_steps["model"]),
            "target": "target_accuracy",
            "primary_metric": {
                "name": "mae",
                "value": regressor_metrics["mae"],
            },
            "metrics": regressor_metrics,
        },
    }
    write_json(model_metadata_path, model_metadata)

    return {
        "raw_csv_path": raw_csv,
        "processed_dir": processed_dir,
        "models_dir": models_dir,
        "cleaning_report": cleaning_report,
        "dataset_metadata_path": metadata_path,
        "model_metadata_path": model_metadata_path,
        "classifier_metrics": classifier_metrics,
        "regressor_metrics": regressor_metrics,
        "classifier_path": classifier_path,
        "regressor_path": regressor_path,
        "classifier_feature_importance": get_model_feature_importance(classifier),
        "regressor_feature_importance": get_model_feature_importance(regressor),
        "split_counts": split_assignment["split_name"].value_counts().to_dict(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the first baseline osu! models.")
    parser.add_argument(
        "--raw-csv",
        type=Path,
        default=None,
        help="Path to the raw flattened dataset CSV. Defaults to the latest run under data/raw/.",
    )
    parser.add_argument(
        "--processed-root",
        type=Path,
        default=Path("data/processed"),
        help="Root directory for processed training artifacts.",
    )
    parser.add_argument(
        "--models-root",
        type=Path,
        default=Path("models"),
        help="Directory for serialized model artifacts.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=DEFAULT_RANDOM_SEED,
        help="Random seed for the grouped user split and baseline models.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_csv = args.raw_csv or find_latest_raw_csv()
    result = run_baseline_training(
        raw_csv_path=raw_csv,
        processed_root=args.processed_root,
        models_root=args.models_root,
        random_seed=args.random_seed,
    )
    summary = {
        "raw_csv_path": str(result["raw_csv_path"]),
        "processed_dir": str(result["processed_dir"]),
        "models_dir": str(result["models_dir"]),
        "split_counts": result["split_counts"],
        "cleaning_report": result["cleaning_report"],
        "classifier_metrics": result["classifier_metrics"],
        "regressor_metrics": result["regressor_metrics"],
        "dataset_metadata_path": str(result["dataset_metadata_path"]),
        "model_metadata_path": str(result["model_metadata_path"]),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
