import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from analysis import false_negatives, predicted_stars, sentiment_band, summarize


@pytest.mark.parametrize(
    ("stars", "expected"),
    [(1, "Negative"), (2, "Negative"), (3, "Neutral"), (4, "Positive"), (5, "Positive")],
)
def test_sentiment_mapping_matches_rubric(stars, expected):
    assert sentiment_band(stars) == expected


def test_label_parser_rejects_out_of_range():
    assert predicted_stars("5 stars") == 5
    with pytest.raises(ValueError):
        predicted_stars("6 stars")


def test_summary_and_false_negatives():
    frame = pd.DataFrame(
        {
            "rating": [5, 4, 3],
            "predicted_stars": [1, 5, 3],
            "sentiment": ["Negative", "Positive", "Neutral"],
        }
    )
    assert false_negatives(frame).index.tolist() == [0]
    assert summarize(frame)["percentage"].sum() == pytest.approx(99.9)
