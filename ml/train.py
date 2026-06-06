from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import joblib
import numpy as np
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
ProgressCallback = Callable[[dict[str, Any]], None]
FLOAT_COMPARISON_ATOL = 1e-9


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def emit_progress(
    progress_callback: ProgressCallback | None,
    *,
    step: int,
    total: int,
    stage: str,
    message: str,
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        {
            "step": step,
            "total": total,
            "stage": stage,
            "message": message,
            "fraction": step / total if total else 1.0,
            "timestamp": iso_now(),
        }
    )


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


def strip_timestamp_fields(payload: dict[str, Any]) -> dict[str, Any]:
    copied = json.loads(json.dumps(payload))
    for key in ["trained_at", "processed_at"]:
        copied.pop(key, None)
    copied.pop("source_processed_dir", None)
    artifacts = copied.get("artifacts")
    if isinstance(artifacts, dict):
        copied["artifacts"] = sorted(artifacts.keys())
    return copied


def metric_dicts_equal(left: dict[str, Any], right: dict[str, Any], atol: float = FLOAT_COMPARISON_ATOL) -> bool:
    return structures_equal(left, right, atol=atol)


def structures_equal(left: Any, right: Any, atol: float = FLOAT_COMPARISON_ATOL) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        if left.keys() != right.keys():
            return False
        return all(structures_equal(left[key], right[key], atol=atol) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return False
        return all(structures_equal(left_item, right_item, atol=atol) for left_item, right_item in zip(left, right))
    if isinstance(left, float) or isinstance(right, float):
        return bool(np.isclose(float(left), float(right), atol=atol, rtol=0.0))
    return left == right


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
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    total_steps = 11
    raw_csv = Path(raw_csv_path) if raw_csv_path else find_latest_raw_csv()
    emit_progress(progress_callback, step=1, total=total_steps, stage="resolve_paths", message="Resolving dataset and artifact paths.")
    processed_dir, models_dir = build_run_paths(raw_csv, Path(processed_root), Path(models_root))
    processed_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    emit_progress(progress_callback, step=2, total=total_steps, stage="load_raw", message="Loading raw dataset CSV.")
    raw_df = pd.read_csv(raw_csv)
    emit_progress(progress_callback, step=3, total=total_steps, stage="clean_raw", message="Validating and cleaning raw rows.")
    cleaned_df, cleaning_report = clean_raw_dataset(raw_df)
    emit_progress(progress_callback, step=4, total=total_steps, stage="split", message="Building grouped train/test split.")
    split_assignment = build_split_assignment(cleaned_df, random_seed=random_seed)
    train_mask = split_assignment["split_name"].eq("train").to_numpy()
    emit_progress(progress_callback, step=5, total=total_steps, stage="feature_engineering", message="Fitting star comfort mapping and engineering features.")
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

    emit_progress(progress_callback, step=6, total=total_steps, stage="train_classifier", message="Training baseline classifier.")
    classifier = build_classifier_pipeline(random_seed=random_seed)
    classifier.fit(X_train, y_class_train)
    emit_progress(progress_callback, step=7, total=total_steps, stage="train_regressor", message="Training baseline regressor.")
    regressor = build_regressor_pipeline(random_seed=random_seed)
    regressor.fit(X_train, y_reg_train)

    emit_progress(progress_callback, step=8, total=total_steps, stage="evaluate", message="Evaluating classifier and regressor metrics.")
    classifier_metrics = evaluate_classifier(classifier, X_test, y_class_test)
    regressor_metrics = evaluate_regressor(regressor, X_test, y_reg_test)

    cleaned_path = processed_dir / "cleaned_dataset.parquet"
    training_path = processed_dir / "training_dataset.parquet"
    split_path = processed_dir / "split_assignment.parquet"
    metadata_path = processed_dir / "dataset_metadata.json"
    emit_progress(progress_callback, step=9, total=total_steps, stage="save_processed", message="Writing processed dataset artifacts.")
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
    emit_progress(progress_callback, step=10, total=total_steps, stage="serialize_models", message="Serializing inference-ready joblib artifacts.")
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
    emit_progress(progress_callback, step=11, total=total_steps, stage="done", message="Baseline training finished.")

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


def load_serialized_models(models_root: str | Path = "models") -> dict[str, Any]:
    models_dir = Path(models_root)
    classifier_path = models_dir / "pass_model.joblib"
    regressor_path = models_dir / "accuracy_model.joblib"
    model_metadata_path = models_dir / "model_metadata.json"
    return {
        "classifier": joblib.load(classifier_path),
        "regressor": joblib.load(regressor_path),
        "metadata": json.loads(model_metadata_path.read_text(encoding="utf-8")),
        "classifier_path": classifier_path,
        "regressor_path": regressor_path,
        "model_metadata_path": model_metadata_path,
    }


def verify_training_reproducibility(
    raw_csv_path: str | Path,
    random_seed: int = DEFAULT_RANDOM_SEED,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    raw_csv = Path(raw_csv_path)
    with tempfile.TemporaryDirectory(prefix="osu-repro-") as temp_dir:
        temp_root = Path(temp_dir)
        emit_progress(progress_callback, step=1, total=8, stage="repro_run_one", message="Running reproducibility pass 1 of 2.")
        run_one = run_baseline_training(
            raw_csv_path=raw_csv,
            processed_root=temp_root / "processed_run_one",
            models_root=temp_root / "models_run_one",
            random_seed=random_seed,
            progress_callback=None,
        )
        emit_progress(progress_callback, step=2, total=8, stage="repro_run_two", message="Running reproducibility pass 2 of 2.")
        run_two = run_baseline_training(
            raw_csv_path=raw_csv,
            processed_root=temp_root / "processed_run_two",
            models_root=temp_root / "models_run_two",
            random_seed=random_seed,
            progress_callback=None,
        )

        emit_progress(progress_callback, step=3, total=8, stage="load_outputs", message="Loading saved split and training artifacts from both runs.")
        split_one = pd.read_parquet(run_one["processed_dir"] / "split_assignment.parquet")
        split_two = pd.read_parquet(run_two["processed_dir"] / "split_assignment.parquet")
        training_one = pd.read_parquet(run_one["processed_dir"] / "training_dataset.parquet")
        training_two = pd.read_parquet(run_two["processed_dir"] / "training_dataset.parquet")
        metadata_one = json.loads(run_one["model_metadata_path"].read_text(encoding="utf-8"))
        metadata_two = json.loads(run_two["model_metadata_path"].read_text(encoding="utf-8"))

        emit_progress(progress_callback, step=4, total=8, stage="load_models", message="Reloading serialized model artifacts from both runs.")
        loaded_one = load_serialized_models(run_one["models_dir"])
        loaded_two = load_serialized_models(run_two["models_dir"])

        emit_progress(progress_callback, step=5, total=8, stage="predict", message="Generating comparison predictions from both serialized pipelines.")
        sample_features_one = training_one[ALL_FEATURE_COLUMNS].head(512)
        sample_features_two = training_two[ALL_FEATURE_COLUMNS].head(512)
        class_proba_one = loaded_one["classifier"].predict_proba(sample_features_one)[:, 1]
        class_proba_two = loaded_two["classifier"].predict_proba(sample_features_two)[:, 1]
        reg_pred_one = loaded_one["regressor"].predict(sample_features_one)
        reg_pred_two = loaded_two["regressor"].predict(sample_features_two)

        emit_progress(progress_callback, step=6, total=8, stage="compare_splits", message="Comparing split assignments and feature-engineered outputs.")
        split_assignment_equal = bool(split_one.equals(split_two))
        training_dataset_equal = bool(training_one.equals(training_two))
        emit_progress(progress_callback, step=7, total=8, stage="compare_metrics", message="Comparing metrics, metadata, and serialized predictions.")
        classifier_metrics_equal = metric_dicts_equal(run_one["classifier_metrics"], run_two["classifier_metrics"])
        regressor_metrics_equal = metric_dicts_equal(run_one["regressor_metrics"], run_two["regressor_metrics"])
        metadata_equal = structures_equal(
            strip_timestamp_fields(metadata_one),
            strip_timestamp_fields(metadata_two),
        )
        classifier_probabilities_equal = bool(np.allclose(class_proba_one, class_proba_two))
        regressor_predictions_equal = bool(np.allclose(reg_pred_one, reg_pred_two))
        emit_progress(progress_callback, step=8, total=8, stage="done", message="Reproducibility check finished.")

        return {
            "raw_csv_path": raw_csv.as_posix(),
            "random_seed": random_seed,
            "split_assignment_equal": split_assignment_equal,
            "training_dataset_equal": training_dataset_equal,
            "classifier_metrics_equal": classifier_metrics_equal,
            "regressor_metrics_equal": regressor_metrics_equal,
            "metadata_equal_ignoring_timestamps": metadata_equal,
            "classifier_probabilities_equal": classifier_probabilities_equal,
            "regressor_predictions_equal": regressor_predictions_equal,
            "run_one_classifier_metrics": run_one["classifier_metrics"],
            "run_one_regressor_metrics": run_one["regressor_metrics"],
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
    parser.add_argument(
        "--verify-reproducibility",
        action="store_true",
        help="Run two training passes in temporary directories and confirm repeatability.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_csv = args.raw_csv or find_latest_raw_csv()
    if args.verify_reproducibility:
        summary = verify_training_reproducibility(raw_csv_path=raw_csv, random_seed=args.random_seed)
        print(json.dumps(summary, indent=2))
        return
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
