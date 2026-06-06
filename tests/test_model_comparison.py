from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
