#!/usr/bin/env python3
"""Train the TrackFlow sales forecast from the repository root."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    from data.forecasting.train import train_sales_forecast

    print(json.dumps(train_sales_forecast(ROOT), indent=2))
