from __future__ import annotations

import json
import time
import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from .evaluate import evaluate_classifier, evaluate_regressor
from .features import (
    ALL_FEATURE_COLUMNS,
    DEFAULT_RANDOM_SEED,
    build_split_assignment,
    clean_raw_dataset,
    engineer_features,
    find_latest_raw_csv,
    fit_star_comfort_mapping,
)
from .pipeline import (
    build_classifier_pipeline,
    build_hist_gradient_boosting_classifier_pipeline,
    build_hist_gradient_boosting_regressor_pipeline,
    build_logistic_regression_pipeline,
    build_regressor_pipeline,
    build_ridge_pipeline,
)
from .train import ProgressCallback, build_run_paths, emit_progress, iso_now, selected_estimator_params, write_json


def build_classifier_candidate_pipelines(random_seed: int = DEFAULT_RANDOM_SEED) -> dict[str, Any]:
    return {
        "RandomForestClassifier": build_classifier_pipeline(random_seed=random_seed),
        "LogisticRegression": build_logistic_regression_pipeline(),
        "HistGradientBoostingClassifier": build_hist_gradient_boosting_classifier_pipeline(random_seed=random_seed),
    }


def build_regressor_candidate_pipelines(random_seed: int = DEFAULT_RANDOM_SEED) -> dict[str, Any]:
    return {
        "RandomForestRegressor": build_regressor_pipeline(random_seed=random_seed),
        "Ridge": build_ridge_pipeline(),
        "HistGradientBoostingRegressor": build_hist_gradient_boosting_regressor_pipeline(random_seed=random_seed),
    }


def _prepare_training_bundle(raw_csv_path: Path, random_seed: int) -> dict[str, Any]:
    raw_df = pd.read_csv(raw_csv_path)
    cleaned_df, cleaning_report = clean_raw_dataset(raw_df)
    split_assignment = build_split_assignment(cleaned_df, random_seed=random_seed)
    train_mask = split_assignment["split_name"].eq("train").to_numpy()
    comfort_mapping = fit_star_comfort_mapping(cleaned_df.iloc[train_mask].copy())
    training_df = engineer_features(cleaned_df, comfort_mapping)

    feature_frame = training_df[ALL_FEATURE_COLUMNS].copy()
    classifier_target = training_df["target_passed"].astype(int)
    regressor_target = training_df["target_accuracy"].astype(float)

    return {
        "raw_df": raw_df,
        "cleaned_df": cleaned_df,
        "training_df": training_df,
        "split_assignment": split_assignment,
        "cleaning_report": cleaning_report,
        "train_mask": train_mask,
        "X_train": feature_frame.loc[train_mask],
        "X_test": feature_frame.loc[~train_mask],
        "y_class_train": classifier_target.loc[train_mask],
        "y_class_test": classifier_target.loc[~train_mask],
        "y_reg_train": regressor_target.loc[train_mask],
        "y_reg_test": regressor_target.loc[~train_mask],
    }


def _fit_and_evaluate_classifier(name: str, pipeline: Any, bundle: dict[str, Any]) -> dict[str, Any]:
    fit_started = time.perf_counter()
    pipeline.fit(bundle["X_train"], bundle["y_class_train"])
    fit_seconds = time.perf_counter() - fit_started

    predict_started = time.perf_counter()
    metrics = evaluate_classifier(pipeline, bundle["X_test"], bundle["y_class_test"])
    predict_seconds = time.perf_counter() - predict_started

    return {
        "model_name": name,
        "task": "classification",
        "primary_metric_name": "pr_auc",
        "primary_metric_value": metrics["pr_auc"],
        "fit_seconds": fit_seconds,
        "predict_seconds": predict_seconds,
        "estimator_params": selected_estimator_params(pipeline.named_steps["model"]),
        **metrics,
    }


def _fit_and_evaluate_regressor(name: str, pipeline: Any, bundle: dict[str, Any]) -> dict[str, Any]:
    fit_started = time.perf_counter()
    pipeline.fit(bundle["X_train"], bundle["y_reg_train"])
    fit_seconds = time.perf_counter() - fit_started

    predict_started = time.perf_counter()
    metrics = evaluate_regressor(pipeline, bundle["X_test"], bundle["y_reg_test"])
    predict_seconds = time.perf_counter() - predict_started

    return {
        "model_name": name,
        "task": "regression",
        "primary_metric_name": "mae",
        "primary_metric_value": metrics["mae"],
        "fit_seconds": fit_seconds,
        "predict_seconds": predict_seconds,
        "estimator_params": selected_estimator_params(pipeline.named_steps["model"]),
        **metrics,
    }


def run_model_comparison(
    raw_csv_path: str | Path | None = None,
    processed_root: str | Path = "data/processed",
    random_seed: int = DEFAULT_RANDOM_SEED,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    raw_csv = Path(raw_csv_path) if raw_csv_path else find_latest_raw_csv()
    processed_dir, _ = build_run_paths(raw_csv, Path(processed_root), Path("models"))
    processed_dir.mkdir(parents=True, exist_ok=True)

    classifier_pipelines = build_classifier_candidate_pipelines(random_seed=random_seed)
    regressor_pipelines = build_regressor_candidate_pipelines(random_seed=random_seed)
    total_steps = 3 + len(classifier_pipelines) + len(regressor_pipelines) + 1

    emit_progress(progress_callback, step=1, total=total_steps, stage="resolve_paths", message="Resolving comparison dataset paths.")
    emit_progress(progress_callback, step=2, total=total_steps, stage="prepare_data", message="Preparing shared cleaned dataset, features, and grouped split.")
    bundle = _prepare_training_bundle(raw_csv, random_seed=random_seed)
    emit_progress(progress_callback, step=3, total=total_steps, stage="bundle_ready", message="Shared train/test bundle is ready for model comparison.")

    classifier_rows: list[dict[str, Any]] = []
    regressor_rows: list[dict[str, Any]] = []
    step = 4

    for name, pipeline in classifier_pipelines.items():
        emit_progress(progress_callback, step=step, total=total_steps, stage="classification", message=f"Training and evaluating {name}.")
        classifier_rows.append(_fit_and_evaluate_classifier(name, pipeline, bundle))
        step += 1

    for name, pipeline in regressor_pipelines.items():
        emit_progress(progress_callback, step=step, total=total_steps, stage="regression", message=f"Training and evaluating {name}.")
        regressor_rows.append(_fit_and_evaluate_regressor(name, pipeline, bundle))
        step += 1

    classifier_results = pd.DataFrame(classifier_rows).sort_values(
        by=["primary_metric_value", "fit_seconds"],
        ascending=[False, True],
    ).reset_index(drop=True)
    regressor_results = pd.DataFrame(regressor_rows).sort_values(
        by=["primary_metric_value", "fit_seconds"],
        ascending=[True, True],
    ).reset_index(drop=True)

    classifier_csv_path = processed_dir / "model_comparison_classifier.csv"
    regressor_csv_path = processed_dir / "model_comparison_regressor.csv"
    summary_json_path = processed_dir / "model_comparison_summary.json"
    classifier_results.to_csv(classifier_csv_path, index=False)
    regressor_results.to_csv(regressor_csv_path, index=False)

    summary_payload = {
        "generated_at": iso_now(),
        "source_raw_csv": raw_csv.as_posix(),
        "random_seed": random_seed,
        "classifier_primary_metric": "pr_auc",
        "regressor_primary_metric": "mae",
        "classifier_winner": classifier_results.iloc[0]["model_name"],
        "regressor_winner": regressor_results.iloc[0]["model_name"],
        "classifier_results_path": classifier_csv_path.as_posix(),
        "regressor_results_path": regressor_csv_path.as_posix(),
        "row_counts": {
            "loaded": int(len(bundle["raw_df"])),
            "cleaned": int(len(bundle["cleaned_df"])),
            "train": int(bundle["train_mask"].sum()),
            "test": int((~bundle["train_mask"]).sum()),
        },
    }
    write_json(summary_json_path, summary_payload)
    emit_progress(progress_callback, step=total_steps, total=total_steps, stage="done", message="Model comparison finished.")

    return {
        "raw_csv_path": raw_csv,
        "processed_dir": processed_dir,
        "classifier_results": classifier_results,
        "regressor_results": regressor_results,
        "summary_path": summary_json_path,
        "classifier_results_path": classifier_csv_path,
        "regressor_results_path": regressor_csv_path,
        "cleaning_report": bundle["cleaning_report"],
        "split_counts": bundle["split_assignment"]["split_name"].value_counts().to_dict(),
        "summary": summary_payload,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the small model comparison pass.")
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
        help="Root directory for processed comparison artifacts.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=DEFAULT_RANDOM_SEED,
        help="Random seed for the grouped user split and candidate models.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_model_comparison(
        raw_csv_path=args.raw_csv,
        processed_root=args.processed_root,
        random_seed=args.random_seed,
    )
    summary = {
        "raw_csv_path": str(result["raw_csv_path"]),
        "processed_dir": str(result["processed_dir"]),
        "classifier_results_path": str(result["classifier_results_path"]),
        "regressor_results_path": str(result["regressor_results_path"]),
        "summary_path": str(result["summary_path"]),
        "classifier_winner": result["summary"]["classifier_winner"],
        "regressor_winner": result["summary"]["regressor_winner"],
        "split_counts": result["split_counts"],
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
