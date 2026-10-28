"""Diagnostic decomposition of the TrackFlow monthly revenue series."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from statsmodels.tsa.seasonal import seasonal_decompose


def save_decomposition(frame: pd.DataFrame, destination: Path) -> None:
    series = frame.set_index("month")["revenue_eur"]
    result = seasonal_decompose(series, model="additive", period=12)
    figure = result.plot()
    figure.set_size_inches(12, 9)
    figure.suptitle("TrackFlow monthly revenue: trend, seasonality, and residual", y=1.01)
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(destination, dpi=150, bbox_inches="tight")
    plt.close(figure)
