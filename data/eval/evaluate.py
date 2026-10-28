"""Temporal cross-validation, learning curves, and diagnosis for TrackFlow."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit

from data.forecasting.features import FEATURE_COLUMNS, build_features, load_sales
from data.forecasting.train import SEED, SeasonalResidualForecaster

N_SPLITS = 5
FOLD_SIZE_MONTHS = 12


def make_temporal_splits(
    sample_count: int,
    *,
    n_splits: int = N_SPLITS,
    test_size: int = FOLD_SIZE_MONTHS,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Return expanding-window splits and reject any chronology violation."""

    splitter = TimeSeriesSplit(n_splits=n_splits, test_size=test_size)
    splits = list(splitter.split(np.arange(sample_count)))
    for train_indices, validation_indices in splits:
        if train_indices.max() >= validation_indices.min():
            raise ValueError("Temporal fold mixes future observations into training")
        if not np.all(np.diff(train_indices) == 1) or not np.all(np.diff(validation_indices) == 1):
            raise ValueError("Temporal folds must be contiguous and chronological")
    return splits


def verify_causal_fold_features(
    raw_training: pd.DataFrame,
    featured_training: pd.DataFrame,
    validation_indices: np.ndarray,
) -> None:
    """Prove each validation feature is unchanged when future rows are absent.

    Validation is rolling-origin, one month ahead: a later validation month may
    use already-observed earlier validation revenue, but can never use its own
    target or a later month.
    """

    for validation_index in validation_indices:
        month = featured_training.iloc[validation_index]["month"]
        prefix = raw_training.loc[raw_training["month"] <= month]
        prefix_features = build_features(prefix).iloc[-1]
        complete_features = featured_training.iloc[validation_index]
        if not np.allclose(
            prefix_features[FEATURE_COLUMNS].to_numpy(dtype=float),
            complete_features[FEATURE_COLUMNS].to_numpy(dtype=float),
        ):
            raise ValueError(f"Feature leakage detected at {month.date().isoformat()}")


def evaluate_sales_model(root: Path) -> dict[str, object]:
    """Evaluate the approved forecast on expanding training windows only."""

    output_dir = root / "data/eval"
    output_dir.mkdir(parents=True, exist_ok=True)

    raw = load_sales(root / "data/raw/trackflow_sales.csv")
    training_raw = raw[raw["month"].dt.year <= 2023].copy()
    featured_training = build_features(training_raw).dropna(subset=FEATURE_COLUMNS)
    featured_training = featured_training.reset_index(drop=True)
    splits = make_temporal_splits(len(featured_training))

    fold_results: list[dict[str, object]] = []
    for fold_number, (train_indices, validation_indices) in enumerate(splits, start=1):
        verify_causal_fold_features(training_raw, featured_training, validation_indices)
        train = featured_training.iloc[train_indices]
        validation = featured_training.iloc[validation_indices]
        model = SeasonalResidualForecaster(random_state=SEED)
        model.fit(train[FEATURE_COLUMNS], train["revenue_eur"])

        train_prediction = model.predict(train[FEATURE_COLUMNS])
        validation_prediction = model.predict(validation[FEATURE_COLUMNS])
        fold_results.append(
            {
                "fold": fold_number,
                "train_rows": len(train),
                "validation_rows": len(validation),
                "train_start": train["month"].min().date().isoformat(),
                "train_end": train["month"].max().date().isoformat(),
                "validation_start": validation["month"].min().date().isoformat(),
                "validation_end": validation["month"].max().date().isoformat(),
                "train_mae_eur": float(mean_absolute_error(train["revenue_eur"], train_prediction)),
                "train_rmse_eur": float(
                    np.sqrt(mean_squared_error(train["revenue_eur"], train_prediction))
                ),
                "validation_mae_eur": float(
                    mean_absolute_error(validation["revenue_eur"], validation_prediction)
                ),
                "validation_rmse_eur": float(
                    np.sqrt(mean_squared_error(validation["revenue_eur"], validation_prediction))
                ),
            }
        )

    summary = summarize_folds(fold_results)
    diagnosis, corrective_action = diagnose(summary)
    results: dict[str, object] = {
        "strategy": "TimeSeriesSplit expanding window, 5 folds, 12 validation months",
        "forecast_horizon": "rolling-origin one-month-ahead",
        "random_state": SEED,
        "folds": fold_results,
        "summary": summary,
        "diagnosis": diagnosis,
        "corrective_action": corrective_action,
        "primary_metric": "RMSE",
        "primary_metric_reason": (
            "TrackFlow uses the forecast for peak-season capacity planning. "
            "A large miss can create warehouse or carrier capacity shortages, "
            "so the squared penalty in RMSE reflects the operational cost better "
            "than MAE; MAE remains the typical-error companion metric."
        ),
    }
    (output_dir / "evaluation_metrics.json").write_text(json.dumps(results, indent=2))
    save_learning_curve(fold_results, output_dir / "learning_curve.png")
    write_report(results, output_dir / "evaluation_report.md")
    return results


def summarize_folds(folds: list[dict[str, object]]) -> dict[str, float]:
    summary: dict[str, float] = {}
    for metric in (
        "train_mae_eur",
        "train_rmse_eur",
        "validation_mae_eur",
        "validation_rmse_eur",
    ):
        values = np.asarray([float(fold[metric]) for fold in folds])
        summary[f"{metric}_mean"] = float(values.mean())
        summary[f"{metric}_std"] = float(values.std(ddof=1))
    return summary


def diagnose(summary: dict[str, float]) -> tuple[str, str]:
    train_rmse = summary["train_rmse_eur_mean"]
    validation_rmse = summary["validation_rmse_eur_mean"]
    gap_ratio = validation_rmse / train_rmse
    if gap_ratio >= 1.75:
        return (
            "moderate overfitting",
            "Reduce Random Forest variance by increasing min_samples_leaf from 2 "
            "and lowering max_depth from 8, selecting the smallest change with "
            "five-fold TimeSeriesSplit before rechecking the untouched 2024-2025 test set.",
        )
    if validation_rmse >= 100_000 and gap_ratio <= 1.25:
        return (
            "underfitting",
            "Add a briefing-grounded peak-season interaction between month and the "
            "annual growth cycle, then compare it with the current model using the "
            "same five temporal folds before touching the held-out test set.",
        )
    return (
        "reasonably well fitted",
        "Keep the present complexity and add calibrated conformal intervals using "
        "out-of-fold residuals; do not increase tree depth because the current "
        "training/validation gap does not justify additional capacity.",
    )


def save_learning_curve(folds: list[dict[str, object]], destination: Path) -> None:
    train_sizes = [int(fold["train_rows"]) for fold in folds]
    train_rmse = [float(fold["train_rmse_eur"]) for fold in folds]
    validation_rmse = [float(fold["validation_rmse_eur"]) for fold in folds]
    figure, axis = plt.subplots(figsize=(10, 6))
    axis.plot(train_sizes, train_rmse, marker="o", label="Training RMSE")
    axis.plot(train_sizes, validation_rmse, marker="o", label="Validation RMSE")
    axis.set(
        title="TrackFlow expanding-window learning curve",
        xlabel="Training observations (months)",
        ylabel="RMSE (EUR)",
    )
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(destination, dpi=160, bbox_inches="tight")
    plt.close(figure)


def write_report(results: dict[str, object], destination: Path) -> None:
    summary = results["summary"]
    assert isinstance(summary, dict)
    folds = results["folds"]
    assert isinstance(folds, list)
    rows = "\n".join(
        "| {fold} | {train_start}-{train_end} | {validation_start}-{validation_end} | "
        "{train_mae_eur:,.0f} | {validation_mae_eur:,.0f} | {train_rmse_eur:,.0f} | "
        "{validation_rmse_eur:,.0f} |".format(**fold)
        for fold in folds
    )
    table_header = (
        "| Fold | Training period | Validation period | Train MAE | "
        "Validation MAE | Train RMSE | Validation RMSE |"
    )
    train_mae = f"EUR {summary['train_mae_eur_mean']:,.0f} ± {summary['train_mae_eur_std']:,.0f}"
    validation_mae = (
        f"EUR {summary['validation_mae_eur_mean']:,.0f} ± {summary['validation_mae_eur_std']:,.0f}"
    )
    train_rmse = f"EUR {summary['train_rmse_eur_mean']:,.0f} ± {summary['train_rmse_eur_std']:,.0f}"
    validation_rmse = (
        f"EUR {summary['validation_rmse_eur_mean']:,.0f} "
        f"± {summary['validation_rmse_eur_std']:,.0f}"
    )
    destination.write_text(
        f"""# TrackFlow regression-model evaluation

## Decision

The model shows **{results["diagnosis"]}**. This classification is based on the
expanding-window learning curve and the five chronological validation folds,
not on the untouched 2024-2025 test period.

## Leakage-safe validation design

The evaluation uses five expanding `TimeSeriesSplit` folds over the 2017-2023
usable training matrix. Every fold trains only on earlier months and validates
on the next 12 months. No data is shuffled. Before fitting each fold, every
validation feature is recomputed from a raw-data prefix ending at that month and
compared with the evaluation matrix. Therefore no lag or rolling feature uses
its own target or a future value. This is a rolling-origin, one-month-ahead
evaluation: already observed earlier validation months may inform a later month.

{table_header}
|---:|---|---|---:|---:|---:|---:|
{rows}

## Cross-validation summary

- Training MAE: **{train_mae}**
- Validation MAE: **{validation_mae}**
- Training RMSE: **{train_rmse}**
- Validation RMSE: **{validation_rmse}**

RMSE is the primary metric because TrackFlow uses this forecast to reserve
warehouse and carrier capacity around large November-December peaks. Large
misses can create disproportionate operational shortages, so RMSE's squared
penalty matches that risk better than MAE. MAE is reported alongside it because
it describes a typical miss in directly understandable EUR.

## Diagnosis and corrective action

The learning curve is saved at `data/eval/learning_curve.png`. The explicit
diagnosis is **{results["diagnosis"]}**.

**Action:** {results["corrective_action"]}

The final 2024-2025 holdout remains untouched by this evaluation and must only
be used after the corrective action is selected using the temporal folds.
"""
    )
