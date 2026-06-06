from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from ml.compare import run_model_comparison


SAMPLE_CSV_PATH = Path("data/sample/osu_ranked_attempts_sample_v1.csv")


class ModelComparisonTests(unittest.TestCase):
    def test_model_comparison_runs_on_sample_dataset(self) -> None:
        with tempfile.TemporaryDirectory(prefix="osu-compare-test-") as temp_dir:
            temp_root = Path(temp_dir)
            result = run_model_comparison(
                raw_csv_path=SAMPLE_CSV_PATH,
                processed_root=temp_root / "processed",
                random_seed=42,
            )

            classifier_names = set(result["classifier_results"]["model_name"].tolist())
            regressor_names = set(result["regressor_results"]["model_name"].tolist())

            self.assertEqual(
                classifier_names,
                {
                    "RandomForestClassifier",
                    "LogisticRegression",
                    "HistGradientBoostingClassifier",
                },
            )
            self.assertEqual(
                regressor_names,
                {
                    "RandomForestRegressor",
                    "Ridge",
                    "HistGradientBoostingRegressor",
                },
            )
            self.assertTrue(result["classifier_results_path"].exists())
            self.assertTrue(result["regressor_results_path"].exists())
            self.assertTrue(result["summary_path"].exists())

    def test_cross_validated_model_comparison_runs_on_sample_dataset(self) -> None:
        with tempfile.TemporaryDirectory(prefix="osu-compare-cv-test-") as temp_dir:
            temp_root = Path(temp_dir)
            result = run_model_comparison(
                raw_csv_path=SAMPLE_CSV_PATH,
                processed_root=temp_root / "processed",
                random_seed=42,
                evaluation_mode="cross_validation",
                cv_folds=2,
            )

            self.assertEqual(result["summary"]["evaluation_mode"], "cross_validation")
            self.assertEqual(result["summary"]["cv_folds_effective"], 2)
            self.assertIn("pr_auc_mean", result["classifier_results"].columns)
            self.assertIn("mae_mean", result["regressor_results"].columns)
            self.assertTrue(result["classifier_results_path"].exists())
            self.assertTrue(result["regressor_results_path"].exists())
            self.assertTrue(result["summary_path"].exists())

    def test_holdout_model_comparison_handles_non_contiguous_cleaned_index(self) -> None:
        with tempfile.TemporaryDirectory(prefix="osu-compare-gap-test-") as temp_dir:
            temp_root = Path(temp_dir)
            temp_csv = temp_root / "with_invalid_row.csv"
            df = pd.read_csv(SAMPLE_CSV_PATH)
            invalid_row = df.iloc[[0]].copy()
            invalid_row = invalid_row.astype({"row_id": "object"})
            invalid_row.loc[:, "beatmap_bpm"] = 0
            invalid_row.loc[:, "row_id"] = invalid_row["row_id"].astype(str) + "-invalid"
            invalid_row.loc[:, "score_id"] = invalid_row["score_id"] + 10_000_000
            pd.concat([df, invalid_row], ignore_index=True).to_csv(temp_csv, index=False)

            result = run_model_comparison(
                raw_csv_path=temp_csv,
                processed_root=temp_root / "processed",
                random_seed=42,
                evaluation_mode="holdout",
            )

            self.assertEqual(result["summary"]["evaluation_mode"], "holdout")
            self.assertGreater(len(result["classifier_results"]), 0)
            self.assertGreater(len(result["regressor_results"]), 0)


if __name__ == "__main__":
    unittest.main()
