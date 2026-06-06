from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline


def safe_roc_auc(y_true: pd.Series, y_score: np.ndarray) -> float | None:
    if pd.Series(y_true).nunique() < 2:
        return None
    return float(roc_auc_score(y_true, y_score))


def evaluate_classifier(model: Pipeline, X_test: pd.DataFrame, y_test: pd.Series) -> dict[str, Any]:
    probabilities = model.predict_proba(X_test)[:, 1]
    predictions = model.predict(X_test)
    return {
        "pr_auc": float(average_precision_score(y_test, probabilities)),
        "roc_auc": safe_roc_auc(y_test, probabilities),
        "f1": float(f1_score(y_test, predictions, zero_division=0)),
        "precision": float(precision_score(y_test, predictions, zero_division=0)),
        "recall": float(recall_score(y_test, predictions, zero_division=0)),
        "positive_rate_test": float(np.mean(y_test)),
        "predicted_positive_rate": float(np.mean(predictions)),
    }


def evaluate_regressor(model: Pipeline, X_test: pd.DataFrame, y_test: pd.Series) -> dict[str, Any]:
    predictions = model.predict(X_test)
    return {
        "mae": float(mean_absolute_error(y_test, predictions)),
        "rmse": float(np.sqrt(mean_squared_error(y_test, predictions))),
        "r2": float(r2_score(y_test, predictions)),
        "prediction_min": float(np.min(predictions)),
        "prediction_max": float(np.max(predictions)),
    }


def get_model_feature_importance(model: Pipeline) -> pd.DataFrame:
    preprocessor = model.named_steps["preprocess"]
    estimator = model.named_steps["model"]
    feature_names = preprocessor.get_feature_names_out()
    importances = getattr(estimator, "feature_importances_", None)
    if importances is None:
        raise ValueError("Model does not expose feature_importances_.")
    frame = pd.DataFrame({"feature": feature_names, "importance": importances})
    return frame.sort_values("importance", ascending=False).reset_index(drop=True)
