from __future__ import annotations

import sys
from pathlib import Path

import joblib
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from train import (  # noqa: E402
    FEATURES,
    N_CLUSTERS,
    build_kmeans,
    label_frame,
    load_housing,
    run_experiment,
    split_housing,
)


@pytest.fixture(scope="module")
def housing() -> pd.DataFrame:
    return load_housing(PROJECT_ROOT / "data" / "raw" / "housing.csv")


def test_official_dataset_is_selected_exactly(housing: pd.DataFrame) -> None:
    assert list(housing.columns) == FEATURES
    assert len(housing) == 20_640
    assert housing.isna().sum().sum() == 0


def test_split_is_deterministic_and_disjoint(housing: pd.DataFrame) -> None:
    first_train, first_test = split_housing(housing)
    second_train, second_test = split_housing(housing)

    assert len(first_train) == 16_512
    assert len(first_test) == 4_128
    assert first_train.index.intersection(first_test.index).empty
    pd.testing.assert_frame_equal(first_train, second_train)
    pd.testing.assert_frame_equal(first_test, second_test)


def test_kmeans_uses_scaling_and_exactly_six_clusters(housing: pd.DataFrame) -> None:
    train, test = split_housing(housing)
    model = build_kmeans().fit(train)
    labelled = label_frame(model, test)

    assert list(model.named_steps) == ["scale", "cluster"]
    assert model.named_steps["cluster"].n_clusters == N_CLUSTERS
    assert str(labelled["cluster"].dtype) == "category"
    assert set(labelled["cluster"].astype(int)) == set(range(N_CLUSTERS))


def test_complete_experiment_saves_both_models_and_evidence(
    housing: pd.DataFrame, tmp_path: Path
) -> None:
    data_path = tmp_path / "housing.csv"
    housing.to_csv(data_path, index=False)
    metrics = run_experiment(data_path, tmp_path)

    assert metrics["n_clusters"] == 6
    assert metrics["supervised_test_metrics"]["accuracy"] >= 0.95
    assert metrics["supervised_test_metrics"]["macro_f1"] >= 0.95
    assert sum(metrics["training_cluster_counts"].values()) == 16_512

    clusterer = joblib.load(tmp_path / "models" / "kmeans_pipeline.joblib")
    classifier = joblib.load(tmp_path / "models" / "cluster_classifier.joblib")
    assert clusterer.predict(housing.head()).shape == (5,)
    assert classifier.predict(housing.head()).shape == (5,)
    assert (tmp_path / "reports" / "figures" / "clusters_train_test.png").stat().st_size > 0
    assert (
        tmp_path / "reports" / "figures" / "classifier_confusion_matrix.png"
    ).stat().st_size > 0
