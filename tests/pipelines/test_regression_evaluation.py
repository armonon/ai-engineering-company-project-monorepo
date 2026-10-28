from __future__ import annotations

from pathlib import Path

import numpy as np

from data.eval.evaluate import make_temporal_splits, verify_causal_fold_features
from data.forecasting.features import FEATURE_COLUMNS, build_features, load_sales

ROOT = Path(__file__).resolve().parents[2]


def test_all_folds_preserve_chronological_order() -> None:
    raw = load_sales(ROOT / "data/raw/trackflow_sales.csv")
    training_raw = raw[raw["month"].dt.year <= 2023].copy()
    featured = build_features(training_raw).dropna(subset=FEATURE_COLUMNS).reset_index(drop=True)
    splits = make_temporal_splits(len(featured))

    assert len(splits) == 5
    previous_validation_end = -1
    for train_indices, validation_indices in splits:
        assert np.all(np.diff(train_indices) == 1)
        assert np.all(np.diff(validation_indices) == 1)
        assert train_indices.max() < validation_indices.min()
        assert previous_validation_end < validation_indices.min()
        assert (
            featured.iloc[train_indices]["month"].max()
            < featured.iloc[validation_indices]["month"].min()
        )
        verify_causal_fold_features(training_raw, featured, validation_indices)
        previous_validation_end = int(validation_indices.max())


def test_future_target_changes_do_not_change_prior_features() -> None:
    raw = load_sales(ROOT / "data/raw/trackflow_sales.csv")
    training_raw = raw[raw["month"].dt.year <= 2023].copy()
    original = build_features(training_raw)
    changed = training_raw.copy()
    changed.loc[changed.index[-1], "revenue_eur"] *= 100
    changed_features = build_features(changed)

    np.testing.assert_allclose(
        original.iloc[:-1][FEATURE_COLUMNS].to_numpy(dtype=float),
        changed_features.iloc[:-1][FEATURE_COLUMNS].to_numpy(dtype=float),
        equal_nan=True,
    )
