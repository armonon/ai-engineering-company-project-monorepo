from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest
from sklearn.pipeline import Pipeline

PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from train import candidate_models, load_reviews, split_reviews  # noqa: E402


def test_official_dataset_contract_and_cleaning():
    frame = load_reviews()

    assert frame.columns.tolist() == ["package_name", "review", "polarity"]
    assert len(frame) == 891
    assert set(frame["polarity"]) == {0, 1}
    assert frame["review"].eq(frame["review"].str.strip().str.lower()).all()


def test_missing_columns_are_rejected(tmp_path: Path):
    path = tmp_path / "invalid.csv"
    pd.DataFrame({"review": ["good"], "polarity": [1]}).to_csv(path, index=False)

    with pytest.raises(ValueError, match="missing required columns"):
        load_reviews(path)


def test_split_is_stratified_disjoint_and_reproducible():
    frame = load_reviews()
    first = split_reviews(frame)
    second = split_reviews(frame)

    assert len(first.x_train) == 623
    assert len(first.x_validation) == 134
    assert len(first.x_test) == 134
    assert set(first.x_train.index).isdisjoint(first.x_validation.index)
    assert set(first.x_train.index).isdisjoint(first.x_test.index)
    assert set(first.x_validation.index).isdisjoint(first.x_test.index)
    assert first.x_test.index.tolist() == second.x_test.index.tolist()

    overall_rate = frame["polarity"].mean()
    for target in (first.y_train, first.y_validation, first.y_test):
        assert target.mean() == pytest.approx(overall_rate, abs=0.02)


def test_every_model_keeps_vectorisation_inside_pipeline():
    models = candidate_models()

    assert {"GaussianNB", "MultinomialNB", "BernoulliNB"}.issubset(models)
    assert {"RandomForest", "LogisticRegression"}.issubset(models)
    assert all(isinstance(model, Pipeline) for model in models.values())
    assert all("vectorizer" in model.named_steps for model in models.values())


@pytest.mark.parametrize("name", ["GaussianNB", "MultinomialNB", "BernoulliNB"])
def test_required_naive_bayes_variants_train_and_predict(name: str):
    frame = load_reviews().iloc[:240]
    split = split_reviews(frame)
    model = candidate_models()[name]

    model.fit(split.x_train, split.y_train)
    predictions = model.predict(split.x_validation)

    assert len(predictions) == len(split.x_validation)
    assert set(predictions).issubset({0, 1})
