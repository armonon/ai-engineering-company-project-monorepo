"""Validated loading and causal feature engineering for monthly sales."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = [
    "month",
    "revenue_eur",
    "shipments_processed",
    "avg_revenue_per_shipment_eur",
    "market",
]
NUMERIC_COLUMNS = [
    "revenue_eur",
    "shipments_processed",
    "avg_revenue_per_shipment_eur",
]
FEATURE_COLUMNS = [
    "revenue_lag_1",
    "revenue_lag_12",
    "revenue_rolling_mean_3",
    "revenue_rolling_std_3",
    "revenue_rolling_mean_12",
    "month_sin",
    "month_cos",
    "quarter",
    "growth_cycle",
    "trend_index",
]


def load_sales(path: Path) -> pd.DataFrame:
    """Load the official TrackFlow CSV and enforce its briefing contract."""

    frame = pd.read_csv(path, na_values=["", "null", "None"])
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing briefing columns: {missing}")

    frame = frame[REQUIRED_COLUMNS].copy()
    frame["month"] = pd.to_datetime(frame["month"], errors="raise")
    frame = frame.sort_values("month").reset_index(drop=True)
    if frame["month"].duplicated().any():
        raise ValueError("Each month must appear exactly once")
    if set(frame["market"].dropna().unique()) != {"consolidated"}:
        raise ValueError("The forecasting model requires consolidated rows only")

    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    # Causal missing-value handling: use only the most recent prior observation.
    frame[NUMERIC_COLUMNS] = frame[NUMERIC_COLUMNS].ffill()
    if frame[REQUIRED_COLUMNS].isna().any().any():
        raise ValueError("Leading or categorical nulls cannot be filled causally")
    if (frame["revenue_eur"] <= 0).any():
        raise ValueError("TrackFlow revenue must always be positive")

    expected = pd.date_range(frame["month"].min(), frame["month"].max(), freq="MS")
    if not frame["month"].equals(pd.Series(expected, name="month")):
        raise ValueError("The monthly series contains a missing or irregular month")
    return frame


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Create time-aware features using only information available before row t."""

    featured = frame.copy()
    past_revenue = featured["revenue_eur"].shift(1)
    featured["revenue_lag_1"] = past_revenue
    featured["revenue_lag_12"] = featured["revenue_eur"].shift(12)
    featured["revenue_rolling_mean_3"] = past_revenue.rolling(3).mean()
    featured["revenue_rolling_std_3"] = past_revenue.rolling(3).std()
    featured["revenue_rolling_mean_12"] = past_revenue.rolling(12).mean()

    month_number = featured["month"].dt.month
    featured["month_sin"] = np.sin(2 * np.pi * month_number / 12)
    featured["month_cos"] = np.cos(2 * np.pi * month_number / 12)
    featured["quarter"] = featured["month"].dt.quarter
    # The briefing documents alternating 3%/9% annual growth. Encode the
    # known calendar cycle without using any future revenue value.
    featured["growth_cycle"] = (featured["month"].dt.year - featured["month"].dt.year.min()) % 2
    featured["trend_index"] = np.arange(len(featured), dtype=float)
    return featured


def split_first_8_last_2(featured: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Drop initial lag rows, then preserve the briefing's exact 8/2-year boundary."""

    years = sorted(featured["month"].dt.year.unique())
    if len(years) != 10:
        raise ValueError(f"Expected exactly 10 calendar years, found {len(years)}")
    train_years = set(years[:8])
    test_years = set(years[-2:])
    usable = featured.dropna(subset=FEATURE_COLUMNS).reset_index(drop=True)
    train = usable[usable["month"].dt.year.isin(train_years)].copy()
    test = usable[usable["month"].dt.year.isin(test_years)].copy()
    if train.empty or test.empty or train["month"].max() >= test["month"].min():
        raise ValueError("Chronological train/test boundary is invalid")
    return train.reset_index(drop=True), test.reset_index(drop=True)
