# Sales forecast delivery review

TrackFlow’s completed forecasting evidence lives under
[`data/forecasting`](../../data/forecasting/README.md). The implementation uses
the exact official dataset at [`data/raw/trackflow_sales.csv`](../../data/raw/trackflow_sales.csv)
and the supplied company briefing at [`trackflow-BRIEFING.md`](./trackflow-BRIEFING.md).

## Rubric map

| Requirement | Evidence |
|---|---|
| Exact company CSV and schema | `data/forecasting/features.py::load_sales` |
| Null handling | causal forward-fill followed by strict validation |
| Trend/seasonal/residual decomposition | `output/decomposition.png` |
| Causal lags and rolling features | `features.py::build_features` + causality test |
| Calendar/seasonal feature | month sin/cos, quarter, growth cycle |
| First 8 years / last 2 years | `split_first_8_last_2` + split test |
| Train-only scaling | fitted `StandardScaler` inside saved forecaster |
| Random Forest with justification | `SeasonalResidualForecaster` and package README |
| MSE, PSI, Gini, K2 on test | `output/metrics.md` / `metrics.json` |
| Forecast + variability area | `output/forecast_vs_actual.png` |
| Fixed seed | `random_state=42` |
| Saved model | `models/trackflow_sales_forecast.joblib` |

The decomposition visibly confirms the briefing: long-term growth,
November–December peaks, and a February trough. The forecast beats the same-month
last-year baseline while the unusually high PSI correctly flags the strong
training/test revenue shift.
