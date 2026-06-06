from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .features import (
    BOOLEAN_FEATURE_COLUMNS,
    CATEGORICAL_FEATURE_COLUMNS,
    DEFAULT_RANDOM_SEED,
    NUMERIC_FEATURE_COLUMNS,
)


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("numeric", "passthrough", NUMERIC_FEATURE_COLUMNS),
            ("boolean", "passthrough", BOOLEAN_FEATURE_COLUMNS),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURE_COLUMNS,
            ),
        ],
        remainder="drop",
    )


def build_scaled_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("numeric", StandardScaler(), NUMERIC_FEATURE_COLUMNS),
            ("boolean", "passthrough", BOOLEAN_FEATURE_COLUMNS),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURE_COLUMNS,
            ),
        ],
        remainder="drop",
    )


def build_classifier_pipeline(random_seed: int = DEFAULT_RANDOM_SEED) -> Pipeline:
    return Pipeline(
        [
            ("preprocess", build_preprocessor()),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=120,
                    max_depth=20,
                    min_samples_leaf=5,
                    random_state=random_seed,
                    n_jobs=-1,
                    class_weight="balanced_subsample",
                ),
            ),
        ]
    )


def build_regressor_pipeline(random_seed: int = DEFAULT_RANDOM_SEED) -> Pipeline:
    return Pipeline(
        [
            ("preprocess", build_preprocessor()),
            (
                "model",
                RandomForestRegressor(
                    n_estimators=120,
                    max_depth=20,
                    min_samples_leaf=5,
                    random_state=random_seed,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def build_logistic_regression_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("preprocess", build_scaled_preprocessor()),
            (
                "model",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                ),
            ),
        ]
    )


def build_ridge_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("preprocess", build_scaled_preprocessor()),
            (
                "model",
                Ridge(
                    alpha=1.0,
                ),
            ),
        ]
    )


def build_hist_gradient_boosting_classifier_pipeline(random_seed: int = DEFAULT_RANDOM_SEED) -> Pipeline:
    return Pipeline(
        [
            ("preprocess", build_preprocessor()),
            (
                "model",
                HistGradientBoostingClassifier(
                    learning_rate=0.1,
                    max_depth=6,
                    max_iter=200,
                    min_samples_leaf=20,
                    random_state=random_seed,
                ),
            ),
        ]
    )


def build_hist_gradient_boosting_regressor_pipeline(random_seed: int = DEFAULT_RANDOM_SEED) -> Pipeline:
    return Pipeline(
        [
            ("preprocess", build_preprocessor()),
            (
                "model",
                HistGradientBoostingRegressor(
                    learning_rate=0.1,
                    max_depth=6,
                    max_iter=200,
                    min_samples_leaf=20,
                    random_state=random_seed,
                ),
            ),
        ]
    )
