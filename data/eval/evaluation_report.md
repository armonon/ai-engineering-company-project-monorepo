# TrackFlow regression-model evaluation

## Decision

The model shows **moderate overfitting**. This classification is based on the
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

| Fold | Training period | Validation period | Train MAE | Validation MAE | Train RMSE | Validation RMSE |
|---:|---|---|---:|---:|---:|---:|
| 1 | 2017-01-01-2018-12-01 | 2019-01-01-2019-12-01 | 10,075 | 63,437 | 12,267 | 73,357 |
| 2 | 2017-01-01-2019-12-01 | 2020-01-01-2020-12-01 | 13,635 | 37,100 | 17,189 | 43,498 |
| 3 | 2017-01-01-2020-12-01 | 2021-01-01-2021-12-01 | 14,446 | 32,353 | 19,184 | 40,904 |
| 4 | 2017-01-01-2021-12-01 | 2022-01-01-2022-12-01 | 14,842 | 38,108 | 19,391 | 47,888 |
| 5 | 2017-01-01-2022-12-01 | 2023-01-01-2023-12-01 | 15,391 | 52,507 | 19,891 | 65,836 |

## Cross-validation summary

- Training MAE: **EUR 13,678 ± 2,113**
- Validation MAE: **EUR 44,701 ± 12,900**
- Training RMSE: **EUR 17,585 ± 3,145**
- Validation RMSE: **EUR 54,296 ± 14,435**

RMSE is the primary metric because TrackFlow uses this forecast to reserve
warehouse and carrier capacity around large November-December peaks. Large
misses can create disproportionate operational shortages, so RMSE's squared
penalty matches that risk better than MAE. MAE is reported alongside it because
it describes a typical miss in directly understandable EUR.

## Diagnosis and corrective action

The learning curve is saved at `data/eval/learning_curve.png`. The explicit
diagnosis is **moderate overfitting**.

**Action:** Reduce Random Forest variance by increasing min_samples_leaf from 2 and lowering max_depth from 8, selecting the smallest change with five-fold TimeSeriesSplit before rechecking the untouched 2024-2025 test set.

The final 2024-2025 holdout remains untouched by this evaluation and must only
be used after the corrective action is selected using the temporal folds.
