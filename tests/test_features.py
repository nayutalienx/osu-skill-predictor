from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from ml.features import (
    ALL_FEATURE_COLUMNS,
    BOOLEAN_FEATURE_COLUMNS,
    build_split_assignment,
    clean_raw_dataset,
    engineer_features,
    fit_star_comfort_mapping,
)


SAMPLE_CSV_PATH = Path("data/sample/osu_ranked_attempts_sample_v1.csv")


class FeatureEngineeringTests(unittest.TestCase):
    def test_sample_dataset_feature_engineering(self) -> None:
        raw_df = pd.read_csv(SAMPLE_CSV_PATH)
        cleaned_df, cleaning_report = clean_raw_dataset(raw_df)

        self.assertEqual(cleaning_report["rows_loaded"], 5)
        self.assertEqual(cleaning_report["rows_kept"], 5)
        self.assertEqual(cleaning_report["rows_dropped_missing_required"], 0)

        split_df = build_split_assignment(cleaned_df, random_seed=42)
        train_mask = split_df["split_name"].eq("train").to_numpy()
        mapping = fit_star_comfort_mapping(cleaned_df.iloc[train_mask].copy())
        featured_df = engineer_features(cleaned_df, mapping)

        for column in ALL_FEATURE_COLUMNS:
            self.assertIn(column, featured_df.columns)

        for column in BOOLEAN_FEATURE_COLUMNS:
            self.assertTrue(set(featured_df[column].unique()).issubset({0, 1}))

        self.assertTrue(featured_df["length_bucket"].isin(["short", "medium", "long"]).all())
        self.assertFalse(featured_df["star_gap"].isna().any())

        hidden_rows = featured_df.loc[featured_df["mods_raw"].str.contains("HD", regex=False)]
        self.assertTrue((hidden_rows["has_hidden"] == 1).all())

        hardrock_rows = featured_df.loc[featured_df["mods_raw"].str.contains("HR", regex=False)]
        self.assertTrue((hardrock_rows["has_hardrock"] == 1).all())

        dt_rows = featured_df.loc[
            featured_df["mods_raw"].str.contains("DT", regex=False)
            | featured_df["mods_raw"].str.contains("NC", regex=False)
        ]
        self.assertTrue((dt_rows["has_doubletime"] == 1).all())


if __name__ == "__main__":
    unittest.main()
