import sys
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from train import NUMERIC_COLUMNS, build_pipeline, coerce_numeric


def test_numeric_coercion_turns_blanks_into_missing_values():
    result = coerce_numeric(pd.DataFrame({"TotalCharges": ["12.50", " "]}))
    assert result.iloc[0, 0] == 12.5
    assert pd.isna(result.iloc[1, 0])


def test_preprocessing_and_classifier_live_in_one_pipeline():
    columns = NUMERIC_COLUMNS + ["Contract", "PaymentMethod"]
    model = build_pipeline(columns)
    assert isinstance(model, Pipeline)
    assert isinstance(model.named_steps["preprocess"], ColumnTransformer)
    assert model.named_steps["classifier"].get_params()["C"] == 1.0
