# TrackFlow sales forecasting

This package implements the company-specific “Sales Forecasting with Time
Series Feature Engineering” project. It loads the official 2016–2025 TrackFlow
monthly revenue dataset, performs a diagnostic seasonal decomposition, builds
causal features, fits an explainable Random Forest forecast, and evaluates only
on the two most recent years.

## Run

From the repository root after `cd services/api && uv sync`:

```bash
services/api/.venv/bin/python scripts/train_sales_model.py
services/api/.venv/bin/python -m pytest tests/pipelines/test_sales_forecast.py -q
```

## Design

- `features.py` validates the exact briefing schema and creates lag-1, lag-12,
  shifted rolling means/standard deviation, cyclical month, quarter, documented
  annual growth-cycle, and trend features.
- `split_first_8_last_2` reserves 2024–2025 as the untouched checking period.
  The first 12 months are unavailable after lag-12 construction, so the usable
  training matrix is 2017–2023 while the split policy still assigns the first
  eight source years (2016–2023) to training.
- `SeasonalResidualForecaster` predicts the correction to the same month one
  year earlier, then adds that correction back to lag-12 revenue. This keeps the
  forecast target in EUR and lets trees continue growth rather than being capped
  by the largest historical target they saw.
- The scaler and forest are fitted on training rows only. Scaling is included
  for an explicit train-only preprocessing contract even though decision trees
  themselves are scale-invariant.

## Honest interpretation

The held-out RMSE is **€56,047 (4.31% of mean test revenue)** versus **€93,184**
for a seasonal-naive forecast. R² is **0.8927** and normalized Gini is **0.9227**.
Residual normality is not rejected (K² = 0.2660, p = 0.8754).

PSI is **9.2454**, far above ordinary stability thresholds. That is expected
warning evidence, not a success metric: the later years have materially higher
revenue because the briefing specifies persistent growth. The provided file has
only consolidated rows, so it cannot independently diagnose the Los Angeles vs.
Zaragoza market mix. A production decision should obtain that missing breakdown.

The plot’s ±1 tree-standard-deviation band covers 50% of test observations. It
shows model variability as required, but it is not a calibrated 95% prediction
interval and must not be presented as one.
