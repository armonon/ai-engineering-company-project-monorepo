# TrackFlow regression evaluation

This folder contains the formal pre-staging evaluation of the approved sales
forecast. Run it from the repository root:

It remains the repository's central location for model, RAG, agent, and
pipeline evaluation artifacts. Future evaluation sets should document their
purpose, construction, and success criteria and must not contain sensitive data.

```bash
services/api/.venv/bin/python scripts/evaluate_sales_model.py
services/api/.venv/bin/python -m pytest tests/pipelines/test_regression_evaluation.py -q
```

## Evaluation contract

- Only the 2016-2023 source period participates in cross-validation. The final
  2024-2025 test period remains untouched.
- Five expanding-window folds each validate on the next 12 months. Nothing is
  shuffled, and every training date precedes every validation date.
- Validation is rolling-origin and one month ahead. The evaluator recomputes
  each validation row from a raw-data prefix to prove lags and rolling features
  cannot use the current target or a future month.
- MAE and RMSE are reported as mean ± sample standard deviation. RMSE is primary
  because large peak-season capacity misses have disproportionate operational
  cost; MAE remains the interpretable typical miss.

## Result

The persistent gap between mean training RMSE (**EUR 17,585**) and validation
RMSE (**EUR 54,296 ± 14,435**) diagnoses **moderate overfitting**. The first
corrective experiment is specific: increase `min_samples_leaf` above 2 and
reduce `max_depth` below 8, selecting only through the same temporal folds.
The untouched test period is not used to choose those values.

## Rubric map

| Requirement | Evidence |
|---|---|
| At least five chronological folds | `make_temporal_splits` and the fold table |
| Explicit no-shuffle/no-mixing verification | `make_temporal_splits` guards and unit test |
| Lag/rolling leakage verification | `verify_causal_fold_features` prefix reconstruction |
| Mean ± standard deviation | `evaluation_metrics.json` and report summary |
| Learning curve saved under `data/eval/` | `learning_curve.png` |
| Training and validation MAE/RMSE | report fold table and summary |
| Company-specific metric justification | report capacity-planning rationale |
| Explicit fit diagnosis | `evaluation_report.md` |
| Specific corrective action | report action tied to Random Forest variance |
| Chronological-order unit test | `tests/pipelines/test_regression_evaluation.py` |

> _Spanish overview: [README.es.md](./README.es.md)._
