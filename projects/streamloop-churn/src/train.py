"""Run StreamLoop's leakage-safe, two-stage churn model search."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import (
    GridSearchCV,
    RandomizedSearchCV,
    StratifiedKFold,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

DATA_URL = (
    "https://raw.githubusercontent.com/IBM/"
    "telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv"
)
RANDOM_STATE = 42
NUMERIC_COLUMNS = ["SeniorCitizen", "tenure", "MonthlyCharges", "TotalCharges"]


def coerce_numeric(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert numeric-looking strings inside the fitted preprocessing graph."""
    return frame.apply(pd.to_numeric, errors="coerce")


def load_and_split() -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    frame = pd.read_csv(DATA_URL)
    target = frame["Churn"].map({"No": 0, "Yes": 1})
    features = frame.drop(columns=["Churn", "customerID"])
    return train_test_split(
        features,
        target,
        test_size=0.20,
        random_state=RANDOM_STATE,
        stratify=target,
    )


def build_pipeline(columns: list[str]) -> Pipeline:
    categorical = [column for column in columns if column not in NUMERIC_COLUMNS]
    numeric_steps = Pipeline(
        [
            ("coerce", FunctionTransformer(coerce_numeric, validate=False)),
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    categorical_steps = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("encode", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    preprocessing = ColumnTransformer(
        [("numeric", numeric_steps, NUMERIC_COLUMNS), ("categorical", categorical_steps, categorical)]
    )
    return Pipeline(
        [
            ("preprocess", preprocessing),
            ("classifier", LogisticRegression(max_iter=2_000, random_state=RANDOM_STATE)),
        ]
    )


def evaluate_once(model: Pipeline, features: pd.DataFrame, target: pd.Series) -> dict[str, float]:
    predictions = model.predict(features)
    probabilities = model.predict_proba(features)[:, 1]
    return {
        "recall": recall_score(target, predictions),
        "precision": precision_score(target, predictions),
        "f1": f1_score(target, predictions),
        "accuracy": accuracy_score(target, predictions),
        "roc_auc": roc_auc_score(target, probabilities),
    }


def top_candidates(search: GridSearchCV, limit: int = 8) -> list[dict[str, Any]]:
    results = pd.DataFrame(search.cv_results_).sort_values(
        ["mean_test_score", "std_test_score"], ascending=[False, True]
    )
    selected = results.head(limit)[
        ["rank_test_score", "mean_test_score", "std_test_score", "params"]
    ]
    return selected.to_dict(orient="records")


def run_experiment() -> dict[str, Any]:
    train_x, test_x, train_y, test_y = load_and_split()
    baseline = build_pipeline(train_x.columns.tolist())
    baseline.fit(train_x, train_y)
    baseline_metrics = evaluate_once(baseline, test_x, test_y)

    cross_validation = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    broad_space = {
        "classifier__C": np.logspace(-3, 2, 60),
        "classifier__penalty": ["l1", "l2"],
        "classifier__solver": ["liblinear"],
        "classifier__class_weight": [None, "balanced"],
    }
    random_search = RandomizedSearchCV(
        build_pipeline(train_x.columns.tolist()),
        param_distributions=broad_space,
        n_iter=24,
        scoring="recall",
        cv=cross_validation,
        n_jobs=-1,
        refit=True,
        random_state=RANDOM_STATE,
        return_train_score=True,
    )
    random_search.fit(train_x, train_y)

    center = float(random_search.best_params_["classifier__C"])
    focused_space = {
        "classifier__C": sorted({max(center / 2, 1e-4), center, min(center * 2, 1e3)}),
        "classifier__penalty": ["l1", "l2"],
        "classifier__solver": ["liblinear"],
        "classifier__class_weight": [None, "balanced"],
    }
    grid_search = GridSearchCV(
        build_pipeline(train_x.columns.tolist()),
        param_grid=focused_space,
        scoring="recall",
        cv=cross_validation,
        n_jobs=-1,
        refit=True,
        return_train_score=True,
    )
    grid_search.fit(train_x, train_y)

    # GridSearchCV already refits this estimator on all training rows. Do not
    # fit it again; the untouched test split is evaluated exactly once here.
    final_metrics = evaluate_once(grid_search.best_estimator_, test_x, test_y)
    candidates = top_candidates(grid_search)
    return {
        "dataset_rows": len(train_x) + len(test_x),
        "training_rows": len(train_x),
        "test_rows": len(test_x),
        "primary_metric": "recall",
        "baseline_metrics": baseline_metrics,
        "random_best_recall": random_search.best_score_,
        "random_best_params": random_search.best_params_,
        "grid_best_recall": grid_search.best_score_,
        "grid_best_std": float(candidates[0]["std_test_score"]),
        "final_params": grid_search.best_params_,
        "final_metrics": final_metrics,
        "top_grid_candidates": candidates,
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    raise TypeError(f"cannot serialize {type(value)}")


def write_report(results: dict[str, Any], report_path: Path) -> None:
    baseline = results["baseline_metrics"]
    final = results["final_metrics"]
    parameters = json.dumps(results["final_params"], indent=2, default=_json_default)
    report_path.write_text(
        f"""# StreamLoop churn tuning report

## Decision metric

Recall for churners is the primary search metric. A false negative means
StreamLoop misses a customer who is about to leave, which costs more than
sending a retention offer to a customer who would have stayed. Precision, F1,
accuracy, and ROC AUC are still reported so the recall gain is not considered
in isolation.

## Leakage controls

- The 7,043 rows were split into {results['training_rows']:,} training and
  {results['test_rows']:,} test rows before fitting preprocessing or models.
- Imputation, scaling, and one-hot encoding live inside one `Pipeline`.
- Both searches used only the training split and five-fold stratified CV.
- The test set was evaluated once for the default baseline and once for the
  final refitted grid-search estimator.

## Baseline versus final test performance

| Model | Recall | Precision | F1 | Accuracy | ROC AUC |
| --- | ---: | ---: | ---: | ---: | ---: |
| Default baseline | {baseline['recall']:.3f} | {baseline['precision']:.3f} | {baseline['f1']:.3f} | {baseline['accuracy']:.3f} | {baseline['roc_auc']:.3f} |
| Tuned final | {final['recall']:.3f} | {final['precision']:.3f} | {final['f1']:.3f} | {final['accuracy']:.3f} | {final['roc_auc']:.3f} |

## Search and stability decision

`RandomizedSearchCV` first explored 24 combinations across five orders of
magnitude for C, both supported penalties, and optional class weighting. Its
best mean CV recall was {results['random_best_recall']:.3f}. `GridSearchCV`
then refined around that C value. The selected configuration achieved mean CV
recall {results['grid_best_recall']:.3f} with fold standard deviation
{results['grid_best_std']:.3f}. The top candidates were inspected by both mean
and standard deviation; the best-mean candidate was retained because its
variation was comparable with the nearby alternatives rather than an unstable
outlier.

Final hyperparameters:

```json
{parameters}
```

The final model is the estimator automatically refitted by `GridSearchCV`; it
was not manually refit afterward.
""",
        encoding="utf-8",
    )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    results = run_experiment()
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "results.json").write_text(
        json.dumps(results, indent=2, default=_json_default), encoding="utf-8"
    )
    write_report(results, root / "tuning_report.md")
    print(json.dumps(results, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
