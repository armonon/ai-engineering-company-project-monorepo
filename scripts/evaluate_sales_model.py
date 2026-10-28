"""Generate TrackFlow's formal regression evaluation artifacts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    from data.eval.evaluate import evaluate_sales_model

    results = evaluate_sales_model(ROOT)
    summary = results["summary"]
    print(f"diagnosis: {results['diagnosis']}")
    print(f"validation RMSE: EUR {summary['validation_rmse_eur_mean']:,.2f}")
