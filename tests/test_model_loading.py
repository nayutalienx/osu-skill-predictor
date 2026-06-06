from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from ml.features import ALL_FEATURE_COLUMNS
from ml.train import load_serialized_models, run_baseline_training, verify_training_reproducibility


SAMPLE_CSV_PATH = Path("data/sample/osu_ranked_attempts_sample_v1.csv")


class ModelArtifactTests(unittest.TestCase):
    def test_joblib_artifacts_load_and_predict(self) -> None:
        with tempfile.TemporaryDirectory(prefix="osu-model-test-") as temp_dir:
            temp_root = Path(temp_dir)
            result = run_baseline_training(
                raw_csv_path=SAMPLE_CSV_PATH,
                processed_root=temp_root / "processed",
                models_root=temp_root / "models",
                random_seed=42,
            )
            loaded = load_serialized_models(temp_root / "models")
            training_df = pd.read_parquet(result["processed_dir"] / "training_dataset.parquet")
            feature_frame = training_df[ALL_FEATURE_COLUMNS]

            classifier_probs = loaded["classifier"].predict_proba(feature_frame)[:, 1]
            regressor_preds = loaded["regressor"].predict(feature_frame)

            self.assertEqual(len(classifier_probs), len(training_df))
            self.assertEqual(len(regressor_preds), len(training_df))
            self.assertTrue(((classifier_probs >= 0.0) & (classifier_probs <= 1.0)).all())
            self.assertTrue(((regressor_preds >= 0.0) & (regressor_preds <= 100.0)).all())
            self.assertEqual(
                loaded["metadata"]["artifacts"]["pass_model"],
                (temp_root / "models" / "pass_model.joblib").as_posix(),
            )

    def test_reproducibility_check_passes_on_sample_dataset(self) -> None:
        report = verify_training_reproducibility(SAMPLE_CSV_PATH, random_seed=42)

        self.assertTrue(report["split_assignment_equal"])
        self.assertTrue(report["training_dataset_equal"])
        self.assertTrue(report["classifier_metrics_equal"])
        self.assertTrue(report["regressor_metrics_equal"])
        self.assertTrue(report["metadata_equal_ignoring_timestamps"])
        self.assertTrue(report["classifier_probabilities_equal"])
        self.assertTrue(report["regressor_predictions_equal"])


if __name__ == "__main__":
    unittest.main()
