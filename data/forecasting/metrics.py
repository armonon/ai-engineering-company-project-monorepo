"""Evaluation metrics required by the sales-forecasting brief."""

from __future__ import annotations

import numpy as np
from scipy.stats import normaltest


def population_stability_index(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Compare train/test target distributions using train-derived quantile bins."""

    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    expected_counts, _ = np.histogram(expected, bins=edges)
    actual_counts, _ = np.histogram(actual, bins=edges)
    epsilon = 1e-6
    expected_share = np.clip(expected_counts / len(expected), epsilon, None)
    actual_share = np.clip(actual_counts / len(actual), epsilon, None)
    return float(np.sum((actual_share - expected_share) * np.log(actual_share / expected_share)))


def normalized_gini(actual: np.ndarray, score: np.ndarray) -> float:
    """Return ranking Gini normalized by the ideal ordering of actual revenue."""

    actual = np.asarray(actual, dtype=float)
    score = np.asarray(score, dtype=float)
    if len(actual) == 0 or actual.sum() <= 0:
        raise ValueError("Gini requires positive actual values")

    def area(ordering: np.ndarray) -> float:
        cumulative = np.cumsum(actual[ordering]) / actual.sum()
        population = np.arange(1, len(actual) + 1) / len(actual)
        return float(np.trapezoid(cumulative - population, population))

    predicted_area = area(np.argsort(-score, kind="stable"))
    ideal_area = area(np.argsort(-actual, kind="stable"))
    return predicted_area / ideal_area if ideal_area else 0.0


def k2_residual_normality(residuals: np.ndarray) -> tuple[float, float]:
    """Return D'Agostino K² statistic and p-value for held-out residuals."""

    result = normaltest(np.asarray(residuals, dtype=float))
    return float(result.statistic), float(result.pvalue)
