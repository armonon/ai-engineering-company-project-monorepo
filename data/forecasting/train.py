"""End-to-end Random Forest sales forecast with honest temporal evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .decomposition import save_decomposition
from .features import FEATURE_COLUMNS, build_features, load_sales, split_first_8_last_2
from .metrics import k2_residual_normality, normalized_gini, population_stability_index

SEED = 42


class SeasonalResidualForecaster(RegressorMixin, BaseEstimator):
    """Forecast revenue as last year's value plus a learned causal correction."""

    def __init__(self, random_state: int = SEED):
        self.random_state = random_state

    def fit(self, features: pd.DataFrame, target: pd.Series):
        self.pipeline_ = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "regressor",
                    RandomForestRegressor(
                        n_estimators=500,
                        max_depth=8,
                        min_samples_leaf=2,
                        max_features=1.0,
                        random_state=self.random_state,
                        n_jobs=-1,
                    ),
                ),
            ]
        )
        residual_target = np.asarray(target) - np.asarray(features["revenue_lag_12"])
        self.pipeline_.fit(features, residual_target)
        return self

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        correction = self.pipeline_.predict(features)
        return np.asarray(features["revenue_lag_12"]) + correction

    def tree_predictions(self, features: pd.DataFrame) -> np.ndarray:
        transformed = self.pipeline_.named_steps["scaler"].transform(features)
        baseline = np.asarray(features["revenue_lag_12"])
        forest = self.pipeline_.named_steps["regressor"]
        return np.vstack([baseline + tree.predict(transformed) for tree in forest.estimators_])


def train_sales_forecast(root: Path) -> dict[str, object]:
    raw_path = root / "data/raw/trackflow_sales.csv"
    output_dir = root / "data/forecasting/output"
    model_dir = root / "data/forecasting/models"
    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    raw = load_sales(raw_path)
    save_decomposition(raw, output_dir / "decomposition.png")
    featured = build_features(raw)
    train, test = split_first_8_last_2(featured)

    x_train, y_train = train[FEATURE_COLUMNS], train["revenue_eur"]
    x_test, y_test = test[FEATURE_COLUMNS], test["revenue_eur"]

    # Random Forest is preferred here because 84 usable training months are a
    # small dataset and Finance prioritizes an explainable bagged-tree baseline
    # over the greater tuning burden and sequential complexity of XGBoost.
    # A seasonal-residual target lets a tree model extend the annual growth
    # trend instead of being capped at historical revenue values. The final
    # prediction remains revenue_eur: lag-12 revenue + learned correction.
    model = SeasonalResidualForecaster(random_state=SEED)
    model.fit(x_train, y_train)
    prediction = model.predict(x_test)

    tree_predictions = model.tree_predictions(x_test)
    variability_std = tree_predictions.std(axis=0)
    lower = np.maximum(0.0, prediction - variability_std)
    upper = prediction + variability_std

    mse = mean_squared_error(y_test, prediction)
    rmse = float(np.sqrt(mse))
    residuals = y_test.to_numpy() - prediction
    k2_statistic, k2_pvalue = k2_residual_normality(residuals)
    metrics: dict[str, object] = {
        "random_state": SEED,
        "raw_rows": len(raw),
        "usable_train_rows": len(train),
        "test_rows": len(test),
        "train_period": [
            train["month"].min().date().isoformat(),
            train["month"].max().date().isoformat(),
        ],
        "test_period": [
            test["month"].min().date().isoformat(),
            test["month"].max().date().isoformat(),
        ],
        "dropped_initial_lag_rows": int(len(raw) - len(train) - len(test)),
        "features": FEATURE_COLUMNS,
        "model": "SeasonalResidualForecaster(RandomForestRegressor)",
        "model_reason": (
            "Small monthly dataset and Finance-facing explainability favor "
            "bagged trees; predicting a correction to lag-12 preserves the EUR "
            "target while allowing continued growth."
        ),
        "seasonal_naive_rmse_eur": float(
            np.sqrt(mean_squared_error(y_test, x_test["revenue_lag_12"]))
        ),
        "mse_eur_squared": float(mse),
        "rmse_eur": rmse,
        "rmse_percent_mean_test_revenue": float(rmse / y_test.mean() * 100),
        "mae_eur": float(mean_absolute_error(y_test, prediction)),
        "r2": float(r2_score(y_test, prediction)),
        "psi_train_vs_test_revenue": population_stability_index(
            y_train.to_numpy(), y_test.to_numpy()
        ),
        "normalized_gini": normalized_gini(y_test.to_numpy(), prediction),
        "k2_residual_statistic": k2_statistic,
        "k2_residual_pvalue": k2_pvalue,
        "variability_band_coverage": float(np.mean((y_test >= lower) & (y_test <= upper))),
    }

    forecast = pd.DataFrame(
        {
            "month": test["month"],
            "actual_revenue_eur": y_test,
            "predicted_revenue_eur": prediction,
            "variability_lower_eur": lower,
            "variability_upper_eur": upper,
            "residual_eur": residuals,
        }
    )
    forecast.to_csv(output_dir / "forecast.csv", index=False)
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    joblib.dump(model, model_dir / "trackflow_sales_forecast.joblib")
    save_forecast_plot(forecast, output_dir / "forecast_vs_actual.png")
    write_metric_report(metrics, output_dir / "metrics.md")
    return metrics


def save_forecast_plot(forecast: pd.DataFrame, destination: Path) -> None:
    dates = pd.to_datetime(forecast["month"])
    figure, axis = plt.subplots(figsize=(13, 6))
    axis.plot(dates, forecast["actual_revenue_eur"], marker="o", label="Actual revenue")
    axis.plot(dates, forecast["predicted_revenue_eur"], marker="o", label="Random Forest forecast")
    axis.fill_between(
        dates,
        forecast["variability_lower_eur"],
        forecast["variability_upper_eur"],
        alpha=0.22,
        label="Tree-to-tree variability (±1 SD)",
    )
    axis.set(
        title="TrackFlow held-out revenue forecast (2024-2025)",
        ylabel="Revenue (EUR)",
        xlabel="Month",
    )
    axis.legend()
    axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(destination, dpi=160, bbox_inches="tight")
    plt.close(figure)


def write_metric_report(metrics: dict[str, object], destination: Path) -> None:
    destination.write_text(
        f"""# TrackFlow sales forecast evaluation

All metrics below are computed on the held-out 2024-2025 test period.

| Metric | Result |
|---|---:|
| MSE | {metrics["mse_eur_squared"]:,.2f} EUR² |
| RMSE | {metrics["rmse_eur"]:,.2f} EUR |
| RMSE / average test revenue | {metrics["rmse_percent_mean_test_revenue"]:.2f}% |
| Seasonal-naive RMSE | {metrics["seasonal_naive_rmse_eur"]:,.2f} EUR |
| MAE | {metrics["mae_eur"]:,.2f} EUR |
| PSI (train vs test revenue) | {metrics["psi_train_vs_test_revenue"]:.4f} |
| Normalized Gini | {metrics["normalized_gini"]:.4f} |
| K² residual statistic | {metrics["k2_residual_statistic"]:.4f} |
| K² residual p-value | {metrics["k2_residual_pvalue"]:.4f} |
| R² | {metrics["r2"]:.4f} |
| ±1 SD variability-band coverage | {metrics["variability_band_coverage"]:.1%} |

## Interpretation

- **MSE** squares misses and therefore emphasizes expensive large errors, but its
  EUR² unit is hard to explain. RMSE restores EUR; its percentage of average
  test revenue gives Finance a direct scale.
- **PSI** compares the historical and held-out revenue distributions. It detects
  material drift that a single average error can conceal. The provided file is
  consolidated only, so it cannot independently measure an LA/Zaragoza mix.
- **Normalized Gini** measures ranking power: whether high-revenue months receive
  higher forecasts than low-revenue months.
- **D'Agostino K²** tests residual normality. A small p-value warns that errors
  retain skew/heavy tails or unmodeled structure.
- Low MSE alone is insufficient: it can coexist with distribution shift, weak
  ranking, biased residuals, or training/test leakage.
"""
    )
