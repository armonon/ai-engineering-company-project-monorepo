"""Train and evaluate the official Google Play review classification project."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.naive_bayes import BernoulliNB, GaussianNB, MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = PROJECT_ROOT / "data" / "raw" / "playstore_reviews.csv"
REQUIRED_COLUMNS = {"package_name", "review", "polarity"}
RANDOM_STATE = 42


@dataclass(frozen=True)
class DatasetSplit:
    """Leakage-safe development, validation, and final test partitions."""

    x_train: pd.Series
    x_validation: pd.Series
    x_test: pd.Series
    y_train: pd.Series
    y_validation: pd.Series
    y_test: pd.Series


def sparse_to_dense(matrix: Any) -> np.ndarray:
    """Convert a sparse token matrix for GaussianNB without a lambda."""

    return matrix.toarray() if hasattr(matrix, "toarray") else np.asarray(matrix)


def load_reviews(path: Path = DEFAULT_DATASET) -> pd.DataFrame:
    """Load and validate the official binary-review dataset."""

    frame = pd.read_csv(path)
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")

    clean = frame.loc[:, ["package_name", "review", "polarity"]].copy()
    if clean.isna().any().any():
        raise ValueError("Dataset contains null package, review, or polarity values.")

    clean["review"] = clean["review"].astype(str).str.strip().str.lower()
    if clean["review"].eq("").any():
        raise ValueError("Dataset contains an empty review after text cleaning.")

    clean["polarity"] = pd.to_numeric(clean["polarity"], errors="raise").astype(int)
    labels = set(clean["polarity"].unique())
    if labels != {0, 1}:
        raise ValueError(f"Polarity must contain exactly 0 and 1; received {sorted(labels)}")
    return clean


def split_reviews(frame: pd.DataFrame) -> DatasetSplit:
    """Create stratified 70/15/15 splits before fitting any transformer."""

    reviews = frame["review"]
    target = frame["polarity"]
    x_development, x_test, y_development, y_test = train_test_split(
        reviews,
        target,
        test_size=0.15,
        random_state=RANDOM_STATE,
        stratify=target,
    )
    validation_share = 0.15 / 0.85
    x_train, x_validation, y_train, y_validation = train_test_split(
        x_development,
        y_development,
        test_size=validation_share,
        random_state=RANDOM_STATE,
        stratify=y_development,
    )
    return DatasetSplit(
        x_train=x_train,
        x_validation=x_validation,
        x_test=x_test,
        y_train=y_train,
        y_validation=y_validation,
        y_test=y_test,
    )


def candidate_models() -> dict[str, Pipeline]:
    """Return the three required NB models and two justified alternatives."""

    return {
        "MultinomialNB": Pipeline(
            [
                ("vectorizer", CountVectorizer(stop_words="english")),
                ("classifier", MultinomialNB()),
            ]
        ),
        "BernoulliNB": Pipeline(
            [
                ("vectorizer", CountVectorizer(stop_words="english", binary=True)),
                ("classifier", BernoulliNB()),
            ]
        ),
        "GaussianNB": Pipeline(
            [
                ("vectorizer", CountVectorizer(stop_words="english", max_features=2_000)),
                ("dense", FunctionTransformer(sparse_to_dense, accept_sparse=True)),
                ("classifier", GaussianNB()),
            ]
        ),
        "RandomForest": Pipeline(
            [
                ("vectorizer", CountVectorizer(stop_words="english", max_features=5_000)),
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=300,
                        min_samples_leaf=2,
                        class_weight="balanced",
                        random_state=RANDOM_STATE,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
        "LogisticRegression": Pipeline(
            [
                (
                    "vectorizer",
                    CountVectorizer(stop_words="english", ngram_range=(1, 2), min_df=2),
                ),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=2_000,
                        class_weight="balanced",
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
    }


def binary_metrics(y_true: pd.Series, predictions: np.ndarray) -> dict[str, Any]:
    """Return deterministic, JSON-safe binary classification metrics."""

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true,
        predictions,
        average="binary",
        zero_division=0,
    )
    return {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "confusion_matrix": confusion_matrix(y_true, predictions).tolist(),
    }


def compare_candidates(split: DatasetSplit) -> tuple[pd.DataFrame, dict[str, Pipeline]]:
    """Fit every candidate on training data and score only on validation."""

    fitted: dict[str, Pipeline] = {}
    rows: list[dict[str, Any]] = []
    for name, pipeline in candidate_models().items():
        pipeline.fit(split.x_train, split.y_train)
        metrics = binary_metrics(split.y_validation, pipeline.predict(split.x_validation))
        fitted[name] = pipeline
        rows.append(
            {
                "model": name,
                **{
                    key: value
                    for key, value in metrics.items()
                    if key != "confusion_matrix"
                },
            }
        )
    comparison = pd.DataFrame(rows).sort_values(["f1", "accuracy"], ascending=False)
    return comparison.reset_index(drop=True), fitted


def tune_multinomial(split: DatasetSplit) -> GridSearchCV:
    """Tune the selected NB family with CV on development data only."""

    x_development = pd.concat([split.x_train, split.x_validation])
    y_development = pd.concat([split.y_train, split.y_validation])
    pipeline = Pipeline(
        [
            ("vectorizer", CountVectorizer(stop_words="english")),
            ("classifier", MultinomialNB()),
        ]
    )
    search = GridSearchCV(
        pipeline,
        {
            "vectorizer__ngram_range": [(1, 1), (1, 2)],
            "vectorizer__min_df": [1, 2, 3],
            "classifier__alpha": [0.25, 0.5, 1.0, 2.0],
        },
        scoring="f1",
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE),
        n_jobs=-1,
        refit=True,
    )
    search.fit(x_development, y_development)
    return search


def informative_tokens(model: Pipeline, count: int = 20) -> pd.DataFrame:
    """Return words with the strongest positive/negative log-odds."""

    vectorizer: CountVectorizer = model.named_steps["vectorizer"]
    classifier: MultinomialNB = model.named_steps["classifier"]
    tokens = np.asarray(vectorizer.get_feature_names_out())
    log_odds = classifier.feature_log_prob_[1] - classifier.feature_log_prob_[0]
    negative = np.argsort(log_odds)[:count]
    positive = np.argsort(log_odds)[-count:][::-1]
    return pd.DataFrame(
        {
            "negative_token": tokens[negative],
            "negative_log_odds": log_odds[negative],
            "positive_token": tokens[positive],
            "positive_log_odds": log_odds[positive],
        }
    )


def save_plots(comparison: pd.DataFrame, y_test: pd.Series, predictions: np.ndarray) -> None:
    """Save reviewer-facing validation and final-test figures."""

    reports = PROJECT_ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    figure, axis = plt.subplots(figsize=(9, 5))
    axis.bar(comparison["model"], comparison["f1"], color="#2563eb")
    axis.set_ylim(0, 1)
    axis.set_ylabel("Positive-class validation F1")
    axis.set_title("Model comparison before final test evaluation")
    axis.tick_params(axis="x", rotation=20)
    figure.tight_layout()
    figure.savefig(reports / "model_comparison.png", dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(5, 5))
    ConfusionMatrixDisplay.from_predictions(
        y_test,
        predictions,
        display_labels=["negative", "positive"],
        cmap="Blues",
        colorbar=False,
        ax=axis,
    )
    axis.set_title("Final held-out test confusion matrix")
    figure.tight_layout()
    figure.savefig(reports / "test_confusion_matrix.png", dpi=160)
    plt.close(figure)


def run_training(dataset: Path = DEFAULT_DATASET) -> dict[str, Any]:
    """Run the complete reproducible project and persist its evidence."""

    frame = load_reviews(dataset)
    split = split_reviews(frame)
    comparison, fitted_candidates = compare_candidates(split)
    search = tune_multinomial(split)
    tuned_naive_bayes: Pipeline = search.best_estimator_
    validation_winner = str(comparison.iloc[0]["model"])
    x_development = pd.concat([split.x_train, split.x_validation])
    y_development = pd.concat([split.y_train, split.y_validation])
    if validation_winner == "MultinomialNB":
        final_model = tuned_naive_bayes
    else:
        final_model = fitted_candidates[validation_winner]
        final_model.fit(x_development, y_development)
    test_predictions = final_model.predict(split.x_test)
    test_metrics = binary_metrics(split.y_test, test_predictions)

    artifacts = PROJECT_ROOT / "artifacts"
    models = PROJECT_ROOT / "models"
    processed = PROJECT_ROOT / "data" / "processed"
    for directory in (artifacts, models, processed):
        directory.mkdir(parents=True, exist_ok=True)

    comparison.to_csv(artifacts / "validation_model_comparison.csv", index=False)
    informative_tokens(tuned_naive_bayes).to_csv(
        artifacts / "informative_tokens.csv", index=False
    )
    pd.DataFrame(
        {
            "review": split.x_test.to_numpy(),
            "actual_polarity": split.y_test.to_numpy(),
            "predicted_polarity": test_predictions,
        }
    ).to_csv(processed / "test_predictions.csv", index=False)
    joblib.dump(final_model, models / "playstore_sentiment.joblib")
    joblib.dump(tuned_naive_bayes, models / "multinomial_naive_bayes.joblib")
    save_plots(comparison, split.y_test, test_predictions)

    report = {
        "dataset": {
            "rows": len(frame),
            "duplicates": int(frame.duplicated().sum()),
            "class_counts": {
                str(key): int(value)
                for key, value in frame["polarity"].value_counts().sort_index().items()
            },
        },
        "splits": {
            "train": len(split.x_train),
            "validation": len(split.x_validation),
            "test": len(split.x_test),
        },
        "selection": {
            "validation_winner": validation_winner,
            "final_model": validation_winner,
            "best_naive_bayes": "MultinomialNB",
            "best_cross_validation_f1": float(search.best_score_),
            "best_parameters": search.best_params_,
        },
        "test": test_metrics,
    }
    (artifacts / "metrics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    report = run_training()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
