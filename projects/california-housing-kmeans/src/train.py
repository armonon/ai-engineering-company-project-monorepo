"""Train and evaluate the California Housing K-means assignment models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import matplotlib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

FEATURES = ["Latitude", "Longitude", "MedInc"]
N_CLUSTERS = 6
RANDOM_STATE = 42
TEST_SIZE = 0.20


def load_housing(path: Path) -> pd.DataFrame:
    """Load the official dataset and return only the assignment features."""
    frame = pd.read_csv(path)
    missing = sorted(set(FEATURES) - set(frame.columns))
    if missing:
        raise ValueError(f"dataset is missing required columns: {', '.join(missing)}")

    selected = frame.loc[:, FEATURES].apply(pd.to_numeric, errors="raise")
    if selected.empty:
        raise ValueError("dataset must contain at least one housing row")
    if selected.isna().any().any() or not np.isfinite(selected.to_numpy()).all():
        raise ValueError("assignment features must contain only finite values")
    return selected


def split_housing(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create one deterministic train/test boundary before fitting models."""
    train, test = train_test_split(
        frame,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        shuffle=True,
    )
    return train.sort_index(), test.sort_index()


def build_kmeans() -> Pipeline:
    """Scale all three features and fit the required six-cluster model."""
    return Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "cluster",
                KMeans(
                    n_clusters=N_CLUSTERS,
                    n_init=20,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def label_frame(model: Pipeline, frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with its predicted cluster stored as a category."""
    labelled = frame.copy()
    labels = model.predict(frame)
    labelled["cluster"] = pd.Categorical(labels, categories=range(N_CLUSTERS))
    return labelled


def build_classifier() -> Pipeline:
    """Build a supervised model for the non-linear six-class boundaries."""
    return Pipeline(
        [
            ("scale", StandardScaler()),
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
    )


def classification_metrics(
    expected: pd.Series, predicted: np.ndarray
) -> dict[str, Any]:
    """Calculate complete multiclass statistics using macro averaging."""
    labels = list(range(N_CLUSTERS))
    return {
        "accuracy": accuracy_score(expected, predicted),
        "macro_precision": precision_score(
            expected, predicted, labels=labels, average="macro", zero_division=0
        ),
        "macro_recall": recall_score(
            expected, predicted, labels=labels, average="macro", zero_division=0
        ),
        "macro_f1": f1_score(
            expected, predicted, labels=labels, average="macro", zero_division=0
        ),
        "confusion_matrix": confusion_matrix(expected, predicted, labels=labels).tolist(),
        "classification_report": classification_report(
            expected,
            predicted,
            labels=labels,
            output_dict=True,
            zero_division=0,
        ),
    }


def plot_clusters(
    train: pd.DataFrame, test: pd.DataFrame, output_path: Path
) -> None:
    """Plot train and held-out cluster predictions on the California map."""
    figure, axis = plt.subplots(figsize=(10, 7))
    train_plot = axis.scatter(
        train["Longitude"],
        train["Latitude"],
        c=train["cluster"].astype(int),
        cmap="tab10",
        s=8,
        alpha=0.38,
        label="Training houses",
    )
    axis.scatter(
        test["Longitude"],
        test["Latitude"],
        c=test["cluster"].astype(int),
        cmap="tab10",
        marker="x",
        s=18,
        linewidths=0.7,
        alpha=0.75,
        label="Held-out houses",
    )
    axis.set(
        title="California housing regions from three-feature-space clusters",
        xlabel="Longitude",
        ylabel="Latitude",
    )
    axis.legend(loc="lower left")
    figure.colorbar(train_plot, ax=axis, ticks=range(N_CLUSTERS), label="Cluster")
    figure.tight_layout()
    figure.savefig(output_path, dpi=180)
    plt.close(figure)


def plot_confusion(expected: pd.Series, predicted: np.ndarray, output_path: Path) -> None:
    """Write a readable held-out confusion matrix."""
    figure, axis = plt.subplots(figsize=(7, 7))
    ConfusionMatrixDisplay.from_predictions(
        expected,
        predicted,
        labels=list(range(N_CLUSTERS)),
        cmap="Blues",
        colorbar=False,
        ax=axis,
    )
    axis.set_title("Supervised reproduction of K-means test labels")
    figure.tight_layout()
    figure.savefig(output_path, dpi=180)
    plt.close(figure)


def run_experiment(data_path: Path, project_root: Path) -> dict[str, Any]:
    """Run the complete rubric workflow and persist its reproducible evidence."""
    frame = load_housing(data_path)
    train, test = split_housing(frame)

    kmeans = build_kmeans()
    kmeans.fit(train)
    labelled_train = label_frame(kmeans, train)
    labelled_test = label_frame(kmeans, test)

    classifier = build_classifier()
    classifier.fit(train, labelled_train["cluster"].astype(int))
    supervised_predictions = classifier.predict(test)
    supervised = classification_metrics(
        labelled_test["cluster"].astype(int), supervised_predictions
    )

    processed = project_root / "data" / "processed"
    models = project_root / "models"
    figures = project_root / "reports" / "figures"
    reports = project_root / "reports"
    for directory in (processed, models, figures, reports):
        directory.mkdir(parents=True, exist_ok=True)

    labelled_train.to_csv(processed / "train_clusters.csv", index_label="source_row")
    labelled_test.to_csv(processed / "test_clusters.csv", index_label="source_row")
    joblib.dump(kmeans, models / "kmeans_pipeline.joblib", compress=3)
    joblib.dump(classifier, models / "cluster_classifier.joblib", compress=3)
    plot_clusters(labelled_train, labelled_test, figures / "clusters_train_test.png")
    plot_confusion(
        labelled_test["cluster"].astype(int),
        supervised_predictions,
        figures / "classifier_confusion_matrix.png",
    )

    cluster_counts = {
        str(int(cluster)): int(count)
        for cluster, count in labelled_train["cluster"].value_counts().sort_index().items()
    }
    centres = kmeans.named_steps["scale"].inverse_transform(
        kmeans.named_steps["cluster"].cluster_centers_
    )
    cluster_centres = {
        str(cluster): {
            feature: float(value) for feature, value in zip(FEATURES, centre, strict=True)
        }
        for cluster, centre in enumerate(centres)
    }
    metrics = {
        "dataset_rows": len(frame),
        "training_rows": len(train),
        "test_rows": len(test),
        "features": FEATURES,
        "n_clusters": N_CLUSTERS,
        "random_state": RANDOM_STATE,
        "kmeans_inertia": float(kmeans.named_steps["cluster"].inertia_),
        "training_cluster_counts": cluster_counts,
        "cluster_centres_original_units": cluster_centres,
        "supervised_model": "RandomForestClassifier",
        "supervised_test_metrics": supervised,
    }
    (reports / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    return metrics


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    metrics = run_experiment(project_root / "data" / "raw" / "housing.csv", project_root)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
