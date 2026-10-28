# TrackFlow sales forecast evaluation

All metrics below are computed on the held-out 2024–2025 test period.

| Metric | Result |
|---|---:|
| MSE | 3,141,295,686.15 EUR² |
| RMSE | 56,047.26 EUR |
| RMSE / average test revenue | 4.31% |
| Seasonal-naive RMSE | 93,184.42 EUR |
| MAE | 44,676.79 EUR |
| PSI (train vs test revenue) | 9.2454 |
| Normalized Gini | 0.9227 |
| K² residual statistic | 0.2660 |
| K² residual p-value | 0.8754 |
| R² | 0.8927 |
| ±1 SD variability-band coverage | 50.0% |

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
