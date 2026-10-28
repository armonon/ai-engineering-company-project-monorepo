from __future__ import annotations

from pathlib import Path

import pytest

from data.forecasting.features import (
    FEATURE_COLUMNS,
    build_features,
    load_sales,
    split_first_8_last_2,
)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/trackflow_sales.csv"


def test_split_respects_first_8_last_2_years_without_leakage() -> None:
    raw = load_sales(RAW)
    train, test = split_first_8_last_2(build_features(raw))

    raw_years = sorted(raw["month"].dt.year.unique())
    train_years = set(train["month"].dt.year)
    test_years = set(test["month"].dt.year)
    assert raw_years == list(range(2016, 2026))
    assert train_years == set(range(2017, 2024))  # 2016 is consumed by lag-12.
    assert test_years == {2024, 2025}
    assert train_years.isdisjoint(test_years)
    assert train["month"].max() < test["month"].min()
    assert len(test) == 24


def test_lag_and_rolling_features_are_strictly_causal() -> None:
    raw = load_sales(RAW)
    featured = build_features(raw)
    for index in range(12, len(featured)):
        assert featured.loc[index, "revenue_lag_1"] == pytest.approx(
            raw.loc[index - 1, "revenue_eur"]
        )
        assert featured.loc[index, "revenue_lag_12"] == pytest.approx(
            raw.loc[index - 12, "revenue_eur"]
        )
        assert featured.loc[index, "revenue_rolling_mean_3"] == pytest.approx(
            raw.loc[index - 3 : index - 1, "revenue_eur"].mean()
        )
        assert featured.loc[index, "revenue_rolling_mean_12"] == pytest.approx(
            raw.loc[index - 12 : index - 1, "revenue_eur"].mean()
        )


def test_official_context_contract_and_feature_set() -> None:
    raw = load_sales(RAW)
    assert len(raw) == 120
    assert set(raw["market"]) == {"consolidated"}
    assert (raw["revenue_eur"] > 0).all()
    assert set(FEATURE_COLUMNS).issubset(build_features(raw).columns)
    assert build_features(raw).loc[0, "growth_cycle"] == 0
    assert build_features(raw).loc[12, "growth_cycle"] == 1
