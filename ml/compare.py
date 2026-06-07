from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold

from .evaluate import evaluate_classifier, evaluate_regressor
from .features import (
    ALL_FEATURE_COLUMNS,
    DEFAULT_RANDOM_SEED,
    build_split_assignment,
    clean_raw_dataset,
    engineer_features,
    find_latest_raw_csv,
    fit_star_comfort_mapping,
    serialize_comfort_mapping,
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


CLASSIFIER_PRIMARY_METRIC = "pr_auc"
REGRESSOR_PRIMARY_METRIC = "mae"


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


def build_classifier_pipeline_by_name(model_name: str, random_seed: int = DEFAULT_RANDOM_SEED) -> Any:
    pipelines = build_classifier_candidate_pipelines(random_seed=random_seed)
    if model_name not in pipelines:
        raise ValueError(f"Unsupported classifier model: {model_name}")
    return pipelines[model_name]


def build_regressor_pipeline_by_name(model_name: str, random_seed: int = DEFAULT_RANDOM_SEED) -> Any:
    pipelines = build_regressor_candidate_pipelines(random_seed=random_seed)
    if model_name not in pipelines:
        raise ValueError(f"Unsupported regressor model: {model_name}")
    return pipelines[model_name]


def prepare_clean_dataset(raw_csv_path: Path) -> dict[str, Any]:
    raw_df = pd.read_csv(raw_csv_path)
    cleaned_df, cleaning_report = clean_raw_dataset(raw_df)
    return {
        "raw_df": raw_df,
        "cleaned_df": cleaned_df,
        "cleaning_report": cleaning_report,
    }


def build_full_training_bundle(cleaned_df: pd.DataFrame) -> dict[str, Any]:
    comfort_mapping = fit_star_comfort_mapping(cleaned_df)
    featured_df = engineer_features(cleaned_df, comfort_mapping)
    return {
        "comfort_mapping": comfort_mapping,
        "featured_df": featured_df,
        "X": featured_df[ALL_FEATURE_COLUMNS].copy(),
        "y_class": featured_df["target_passed"].astype(int),
        "y_reg": featured_df["target_accuracy"].astype(float),
    }


def build_feature_bundle_for_indices(
    cleaned_df: pd.DataFrame,
    train_indices: list[int] | pd.Index | Any,
    test_indices: list[int] | pd.Index | Any,
) -> dict[str, Any]:
    train_df = cleaned_df.iloc[train_indices].copy()
    test_df = cleaned_df.iloc[test_indices].copy()
    comfort_mapping = fit_star_comfort_mapping(train_df)
    train_featured = engineer_features(train_df, comfort_mapping)
    test_featured = engineer_features(test_df, comfort_mapping)

    return {
        "train_featured": train_featured,
        "test_featured": test_featured,
        "X_train": train_featured[ALL_FEATURE_COLUMNS].copy(),
        "X_test": test_featured[ALL_FEATURE_COLUMNS].copy(),
        "y_class_train": train_featured["target_passed"].astype(int),
        "y_class_test": test_featured["target_passed"].astype(int),
        "y_reg_train": train_featured["target_accuracy"].astype(float),
        "y_reg_test": test_featured["target_accuracy"].astype(float),
    }


def prepare_holdout_bundle(cleaned_df: pd.DataFrame, random_seed: int) -> dict[str, Any]:
    split_assignment = build_split_assignment(cleaned_df, random_seed=random_seed)
    split_names = split_assignment["split_name"].to_numpy()
    train_positions = (split_names == "train").nonzero()[0]
    test_positions = (split_names == "test").nonzero()[0]
    feature_bundle = build_feature_bundle_for_indices(cleaned_df, train_positions, test_positions)
    return {
        "split_assignment": split_assignment,
        "train_positions": train_positions.tolist(),
        "test_positions": test_positions.tolist(),
        **feature_bundle,
    }


def fit_and_evaluate_classifier_holdout(name: str, pipeline: Any, bundle: dict[str, Any]) -> dict[str, Any]:
    fit_started = time.perf_counter()
    pipeline.fit(bundle["X_train"], bundle["y_class_train"])
    fit_seconds = time.perf_counter() - fit_started

    predict_started = time.perf_counter()
    metrics = evaluate_classifier(pipeline, bundle["X_test"], bundle["y_class_test"])
    predict_seconds = time.perf_counter() - predict_started

    return {
        "model_name": name,
        "task": "classification",
        "evaluation_mode": "holdout",
        "primary_metric_name": CLASSIFIER_PRIMARY_METRIC,
        "primary_metric_value": metrics[CLASSIFIER_PRIMARY_METRIC],
        "fit_seconds": fit_seconds,
        "predict_seconds": predict_seconds,
        "estimator_params": selected_estimator_params(pipeline.named_steps["model"]),
        **metrics,
    }


def fit_and_evaluate_regressor_holdout(name: str, pipeline: Any, bundle: dict[str, Any]) -> dict[str, Any]:
    fit_started = time.perf_counter()
    pipeline.fit(bundle["X_train"], bundle["y_reg_train"])
    fit_seconds = time.perf_counter() - fit_started

    predict_started = time.perf_counter()
    metrics = evaluate_regressor(pipeline, bundle["X_test"], bundle["y_reg_test"])
    predict_seconds = time.perf_counter() - predict_started

    return {
        "model_name": name,
        "task": "regression",
        "evaluation_mode": "holdout",
        "primary_metric_name": REGRESSOR_PRIMARY_METRIC,
        "primary_metric_value": metrics[REGRESSOR_PRIMARY_METRIC],
        "fit_seconds": fit_seconds,
        "predict_seconds": predict_seconds,
        "estimator_params": selected_estimator_params(pipeline.named_steps["model"]),
        **metrics,
    }


def _mean_or_none(series: pd.Series) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return float(valid.mean())


def _std_or_none(series: pd.Series) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return float(valid.std(ddof=0))


def aggregate_cv_results(rows: list[dict[str, Any]], *, task: str, primary_metric_name: str) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    grouped_rows: list[dict[str, Any]] = []
    metric_columns = [
        column
        for column in frame.columns
        if column
        not in {
            "model_name",
            "fold_index",
            "task",
            "evaluation_mode",
            "estimator_params",
            "primary_metric_name",
        }
    ]
    for model_name, group in frame.groupby("model_name", sort=False):
        row: dict[str, Any] = {
            "model_name": model_name,
            "task": task,
            "evaluation_mode": "cross_validation",
            "fold_count": int(len(group)),
            "primary_metric_name": primary_metric_name,
            "primary_metric_value": _mean_or_none(group[primary_metric_name]),
            "estimator_params": group["estimator_params"].iloc[0],
        }
        for column in metric_columns:
            row[f"{column}_mean"] = _mean_or_none(group[column])
            row[f"{column}_std"] = _std_or_none(group[column])
        grouped_rows.append(row)

    ascending = task == "regression"
    return pd.DataFrame(grouped_rows).sort_values(
        by=["primary_metric_value", "fit_seconds_mean"],
        ascending=[ascending, True],
    ).reset_index(drop=True)


def run_holdout_model_comparison(
    raw_csv: Path,
    processed_dir: Path,
    random_seed: int,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    classifier_pipelines = build_classifier_candidate_pipelines(random_seed=random_seed)
    regressor_pipelines = build_regressor_candidate_pipelines(random_seed=random_seed)
    total_steps = 3 + len(classifier_pipelines) + len(regressor_pipelines) + 1

    emit_progress(progress_callback, step=1, total=total_steps, stage="resolve_paths", message="Resolving comparison dataset paths.")
    emit_progress(progress_callback, step=2, total=total_steps, stage="prepare_data", message="Preparing shared cleaned dataset, features, and grouped holdout split.")
    prepared = prepare_clean_dataset(raw_csv)
    bundle = prepare_holdout_bundle(prepared["cleaned_df"], random_seed=random_seed)
    emit_progress(progress_callback, step=3, total=total_steps, stage="bundle_ready", message="Shared holdout bundle is ready for model comparison.")

    classifier_rows: list[dict[str, Any]] = []
    regressor_rows: list[dict[str, Any]] = []
    step = 4

    for name, pipeline in classifier_pipelines.items():
        emit_progress(progress_callback, step=step, total=total_steps, stage="classification", message=f"Training and evaluating {name}.")
        classifier_rows.append(fit_and_evaluate_classifier_holdout(name, pipeline, bundle))
        step += 1

    for name, pipeline in regressor_pipelines.items():
        emit_progress(progress_callback, step=step, total=total_steps, stage="regression", message=f"Training and evaluating {name}.")
        regressor_rows.append(fit_and_evaluate_regressor_holdout(name, pipeline, bundle))
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
        "evaluation_mode": "holdout",
        "random_seed": random_seed,
        "classifier_primary_metric": CLASSIFIER_PRIMARY_METRIC,
        "regressor_primary_metric": REGRESSOR_PRIMARY_METRIC,
        "classifier_winner": classifier_results.iloc[0]["model_name"],
        "regressor_winner": regressor_results.iloc[0]["model_name"],
        "classifier_results_path": classifier_csv_path.as_posix(),
        "regressor_results_path": regressor_csv_path.as_posix(),
        "row_counts": {
            "loaded": int(len(prepared["raw_df"])),
            "cleaned": int(len(prepared["cleaned_df"])),
            "train": int(len(bundle["train_positions"])),
            "test": int(len(bundle["test_positions"])),
        },
    }
    write_json(summary_json_path, summary_payload)
    emit_progress(progress_callback, step=total_steps, total=total_steps, stage="done", message="Holdout model comparison finished.")

    return {
        "raw_csv_path": raw_csv,
        "processed_dir": processed_dir,
        "classifier_results": classifier_results,
        "regressor_results": regressor_results,
        "summary_path": summary_json_path,
        "classifier_results_path": classifier_csv_path,
        "regressor_results_path": regressor_csv_path,
        "cleaning_report": prepared["cleaning_report"],
        "split_counts": bundle["split_assignment"]["split_name"].value_counts().to_dict(),
        "summary": summary_payload,
    }


def run_cross_validated_model_comparison(
    raw_csv: Path,
    processed_dir: Path,
    random_seed: int,
    cv_folds: int = 5,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    prepared = prepare_clean_dataset(raw_csv)
    cleaned_df = prepared["cleaned_df"].reset_index(drop=True)
    groups = cleaned_df["user_id"].to_numpy()
    classifier_target = cleaned_df["target_passed"].astype(int).to_numpy()

    unique_groups = cleaned_df["user_id"].nunique()
    effective_folds = max(2, min(cv_folds, unique_groups))
    classifier_splitter = StratifiedGroupKFold(n_splits=effective_folds, shuffle=True, random_state=random_seed)
    regressor_splitter = GroupKFold(n_splits=effective_folds)
    classifier_pipelines = build_classifier_candidate_pipelines(random_seed=random_seed)
    regressor_pipelines = build_regressor_candidate_pipelines(random_seed=random_seed)

    total_steps = 2 + (effective_folds * len(classifier_pipelines)) + (effective_folds * len(regressor_pipelines)) + 1
    emit_progress(progress_callback, step=1, total=total_steps, stage="resolve_paths", message="Resolving cross-validation dataset paths.")
    emit_progress(progress_callback, step=2, total=total_steps, stage="prepare_data", message=f"Preparing cleaned dataset for grouped cross-validation with {effective_folds} folds.")

    classifier_fold_rows: list[dict[str, Any]] = []
    regressor_fold_rows: list[dict[str, Any]] = []
    step = 3

    for fold_index, (train_idx, test_idx) in enumerate(
        classifier_splitter.split(cleaned_df, classifier_target, groups=groups),
        start=1,
    ):
        feature_bundle = build_feature_bundle_for_indices(cleaned_df, train_idx, test_idx)
        for model_name, pipeline in build_classifier_candidate_pipelines(random_seed=random_seed).items():
            emit_progress(
                progress_callback,
                step=step,
                total=total_steps,
                stage="classification_cv",
                message=f"Fold {fold_index}/{effective_folds}: training {model_name}.",
            )
            row = fit_and_evaluate_classifier_holdout(model_name, pipeline, feature_bundle)
            row["fold_index"] = fold_index
            classifier_fold_rows.append(row)
            step += 1

    for fold_index, (train_idx, test_idx) in enumerate(
        regressor_splitter.split(cleaned_df, groups=groups),
        start=1,
    ):
        feature_bundle = build_feature_bundle_for_indices(cleaned_df, train_idx, test_idx)
        for model_name, pipeline in build_regressor_candidate_pipelines(random_seed=random_seed).items():
            emit_progress(
                progress_callback,
                step=step,
                total=total_steps,
                stage="regression_cv",
                message=f"Fold {fold_index}/{effective_folds}: training {model_name}.",
            )
            row = fit_and_evaluate_regressor_holdout(model_name, pipeline, feature_bundle)
            row["fold_index"] = fold_index
            regressor_fold_rows.append(row)
            step += 1

    classifier_fold_results = pd.DataFrame(classifier_fold_rows)
    regressor_fold_results = pd.DataFrame(regressor_fold_rows)
    classifier_results = aggregate_cv_results(
        classifier_fold_rows,
        task="classification",
        primary_metric_name=CLASSIFIER_PRIMARY_METRIC,
    )
    regressor_results = aggregate_cv_results(
        regressor_fold_rows,
        task="regression",
        primary_metric_name=REGRESSOR_PRIMARY_METRIC,
    )

    classifier_csv_path = processed_dir / "model_comparison_cv_classifier.csv"
    regressor_csv_path = processed_dir / "model_comparison_cv_regressor.csv"
    classifier_folds_path = processed_dir / "model_comparison_cv_classifier_folds.csv"
    regressor_folds_path = processed_dir / "model_comparison_cv_regressor_folds.csv"
    summary_json_path = processed_dir / "model_comparison_cv_summary.json"
    classifier_results.to_csv(classifier_csv_path, index=False)
    regressor_results.to_csv(regressor_csv_path, index=False)
    classifier_fold_results.to_csv(classifier_folds_path, index=False)
    regressor_fold_results.to_csv(regressor_folds_path, index=False)

    summary_payload = {
        "generated_at": iso_now(),
        "source_raw_csv": raw_csv.as_posix(),
        "evaluation_mode": "cross_validation",
        "random_seed": random_seed,
        "cv_folds_requested": cv_folds,
        "cv_folds_effective": effective_folds,
        "classifier_primary_metric": CLASSIFIER_PRIMARY_METRIC,
        "regressor_primary_metric": REGRESSOR_PRIMARY_METRIC,
        "classifier_winner": classifier_results.iloc[0]["model_name"],
        "regressor_winner": regressor_results.iloc[0]["model_name"],
        "classifier_results_path": classifier_csv_path.as_posix(),
        "regressor_results_path": regressor_csv_path.as_posix(),
        "classifier_fold_results_path": classifier_folds_path.as_posix(),
        "regressor_fold_results_path": regressor_folds_path.as_posix(),
        "row_counts": {
            "loaded": int(len(prepared["raw_df"])),
            "cleaned": int(len(cleaned_df)),
            "unique_users": int(cleaned_df["user_id"].nunique()),
        },
    }
    write_json(summary_json_path, summary_payload)
    emit_progress(progress_callback, step=total_steps, total=total_steps, stage="done", message="Cross-validation model comparison finished.")

    return {
        "raw_csv_path": raw_csv,
        "processed_dir": processed_dir,
        "classifier_results": classifier_results,
        "regressor_results": regressor_results,
        "classifier_fold_results": classifier_fold_results,
        "regressor_fold_results": regressor_fold_results,
        "summary_path": summary_json_path,
        "classifier_results_path": classifier_csv_path,
        "regressor_results_path": regressor_csv_path,
        "cleaning_report": prepared["cleaning_report"],
        "split_counts": {"cv_folds": effective_folds},
        "summary": summary_payload,
    }


def run_model_comparison(
    raw_csv_path: str | Path | None = None,
    processed_root: str | Path = "data/processed",
    random_seed: int = DEFAULT_RANDOM_SEED,
    evaluation_mode: str = "holdout",
    cv_folds: int = 5,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    raw_csv = Path(raw_csv_path) if raw_csv_path else find_latest_raw_csv()
    processed_dir, _ = build_run_paths(raw_csv, Path(processed_root), Path("models"))
    processed_dir.mkdir(parents=True, exist_ok=True)

    if evaluation_mode == "holdout":
        return run_holdout_model_comparison(
            raw_csv=raw_csv,
            processed_dir=processed_dir,
            random_seed=random_seed,
            progress_callback=progress_callback,
        )
    if evaluation_mode == "cross_validation":
        return run_cross_validated_model_comparison(
            raw_csv=raw_csv,
            processed_dir=processed_dir,
            random_seed=random_seed,
            cv_folds=cv_folds,
            progress_callback=progress_callback,
        )
    raise ValueError(f"Unsupported evaluation_mode: {evaluation_mode}")


def _winner_metric_snapshot(result_df: pd.DataFrame, *, task: str) -> dict[str, Any]:
    metric_name = CLASSIFIER_PRIMARY_METRIC if task == "classification" else REGRESSOR_PRIMARY_METRIC
    metric_column = metric_name if metric_name in result_df.columns else f"{metric_name}_mean"
    ascending = task == "regression"
    winner = result_df.sort_values(by=[metric_column], ascending=ascending).iloc[0]
    return {
        "metric_name": metric_column,
        "metric_value": float(winner[metric_column]),
    }


def save_winner_models(
    comparison_result: dict[str, Any],
    *,
    models_root: str | Path = "models",
    random_seed: int | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    raw_csv = Path(comparison_result["raw_csv_path"])
    models_dir = Path(models_root)
    models_dir.mkdir(parents=True, exist_ok=True)

    result_seed = comparison_result["summary"].get("random_seed", DEFAULT_RANDOM_SEED)
    chosen_seed = result_seed if random_seed is None else random_seed

    total_steps = 6
    emit_progress(progress_callback, step=1, total=total_steps, stage="load_raw", message="Loading raw dataset for winner-model serialization.")
    prepared = prepare_clean_dataset(raw_csv)
    emit_progress(progress_callback, step=2, total=total_steps, stage="feature_engineering", message="Engineering full-dataset features for final winner training.")
    training_bundle = build_full_training_bundle(prepared["cleaned_df"])

    classifier_name = str(comparison_result["summary"]["classifier_winner"])
    regressor_name = str(comparison_result["summary"]["regressor_winner"])
    classifier = build_classifier_pipeline_by_name(classifier_name, random_seed=chosen_seed)
    regressor = build_regressor_pipeline_by_name(regressor_name, random_seed=chosen_seed)

    emit_progress(progress_callback, step=3, total=total_steps, stage="train_classifier", message=f"Training final classifier artifact: {classifier_name}.")
    classifier.fit(training_bundle["X"], training_bundle["y_class"])
    emit_progress(progress_callback, step=4, total=total_steps, stage="train_regressor", message=f"Training final regressor artifact: {regressor_name}.")
    regressor.fit(training_bundle["X"], training_bundle["y_reg"])

    classifier_path = models_dir / "pass_model.joblib"
    regressor_path = models_dir / "accuracy_model.joblib"
    metadata_path = models_dir / "model_metadata.json"
    emit_progress(progress_callback, step=5, total=total_steps, stage="serialize_models", message="Writing canonical model artifacts to models/.")
    joblib.dump(classifier, classifier_path)
    joblib.dump(regressor, regressor_path)

    classifier_metrics = _winner_metric_snapshot(comparison_result["classifier_results"], task="classification")
    regressor_metrics = _winner_metric_snapshot(comparison_result["regressor_results"], task="regression")
    metadata = {
        "artifact_version": "v2_comparison_winner",
        "trained_at": iso_now(),
        "source_raw_csv": raw_csv.as_posix(),
        "training_scope": "full_cleaned_dataset",
        "feature_columns": ALL_FEATURE_COLUMNS,
        "target_columns": ["target_passed", "target_accuracy"],
        "star_comfort_mapping": serialize_comfort_mapping(training_bundle["comfort_mapping"]),
        "artifacts": {
            "pass_model": classifier_path.as_posix(),
            "accuracy_model": regressor_path.as_posix(),
        },
        "row_counts": {
            "loaded": int(len(prepared["raw_df"])),
            "cleaned": int(len(prepared["cleaned_df"])),
            "unique_users": int(prepared["cleaned_df"]["user_id"].nunique()),
            "unique_beatmaps": int(prepared["cleaned_df"]["beatmap_id"].nunique()),
        },
        "cleaning_report": prepared["cleaning_report"],
        "model_selection": {
            "evaluation_mode": comparison_result["summary"]["evaluation_mode"],
            "random_seed": chosen_seed,
            "comparison_summary_path": Path(comparison_result["summary_path"]).as_posix(),
            "classifier_winner": classifier_name,
            "regressor_winner": regressor_name,
        },
        "classifier": {
            "estimator": classifier_name,
            "estimator_params": selected_estimator_params(classifier.named_steps["model"]),
            "target": "target_passed",
            "primary_metric": classifier_metrics,
        },
        "regressor": {
            "estimator": regressor_name,
            "estimator_params": selected_estimator_params(regressor.named_steps["model"]),
            "target": "target_accuracy",
            "primary_metric": regressor_metrics,
            "prediction_postprocess": {
                "note": "Model predictions are not clipped inside the serialized pipeline.",
                "recommended_clip_range": [0.0, 100.0],
            },
        },
    }
    write_json(metadata_path, metadata)
    emit_progress(progress_callback, step=6, total=total_steps, stage="done", message="Winner models saved to models/.")

    return {
        "models_dir": models_dir,
        "classifier_path": classifier_path,
        "regressor_path": regressor_path,
        "model_metadata_path": metadata_path,
        "classifier_model_name": classifier_name,
        "regressor_model_name": regressor_name,
        "metadata": metadata,
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
    parser.add_argument(
        "--evaluation-mode",
        choices=["holdout", "cross_validation"],
        default="holdout",
        help="Evaluation mode for the comparison pass.",
    )
    parser.add_argument(
        "--cv-folds",
        type=int,
        default=5,
        help="Requested fold count for grouped cross-validation mode.",
    )
    parser.add_argument(
        "--save-winners",
        action="store_true",
        help="After comparison, retrain the selected winners on the full cleaned dataset and save canonical model artifacts.",
    )
    parser.add_argument(
        "--models-root",
        type=Path,
        default=Path("models"),
        help="Directory for canonical serialized winner-model artifacts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_model_comparison(
        raw_csv_path=args.raw_csv,
        processed_root=args.processed_root,
        random_seed=args.random_seed,
        evaluation_mode=args.evaluation_mode,
        cv_folds=args.cv_folds,
    )
    saved_models = None
    if args.save_winners:
        saved_models = save_winner_models(
            result,
            models_root=args.models_root,
            random_seed=args.random_seed,
        )
    summary = {
        "raw_csv_path": str(result["raw_csv_path"]),
        "processed_dir": str(result["processed_dir"]),
        "classifier_results_path": str(result["classifier_results_path"]),
        "regressor_results_path": str(result["regressor_results_path"]),
        "summary_path": str(result["summary_path"]),
        "evaluation_mode": result["summary"]["evaluation_mode"],
        "classifier_winner": result["summary"]["classifier_winner"],
        "regressor_winner": result["summary"]["regressor_winner"],
        "split_counts": result["split_counts"],
    }
    if saved_models is not None:
        summary["saved_models"] = {
            "models_dir": str(saved_models["models_dir"]),
            "classifier_path": str(saved_models["classifier_path"]),
            "regressor_path": str(saved_models["regressor_path"]),
            "model_metadata_path": str(saved_models["model_metadata_path"]),
        }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
