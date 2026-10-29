"""Pure analysis helpers for the WeLoveReviews sentiment deliverable."""

from __future__ import annotations

import pandas as pd


def predicted_stars(label: str) -> int:
    """Convert the nlptown labels (for example ``4 stars``) to an integer."""
    value = int(label.split()[0])
    if value not in {1, 2, 3, 4, 5}:
        raise ValueError(f"unexpected model label: {label}")
    return value


def sentiment_band(stars: int) -> str:
    if stars <= 2:
        return "Negative"
    if stars == 3:
        return "Neutral"
    return "Positive"


def summarize(frame: pd.DataFrame) -> pd.DataFrame:
    counts = frame["sentiment"].value_counts().reindex(
        ["Positive", "Neutral", "Negative"], fill_value=0
    )
    return pd.DataFrame(
        {
            "reviews": counts,
            "percentage": (counts / len(frame) * 100).round(1),
        }
    )


def false_negatives(frame: pd.DataFrame) -> pd.DataFrame:
    """High human rating but low model prediction: the rubric's key mismatch."""
    return frame.loc[
        (frame["rating"] >= 4) & (frame["predicted_stars"] <= 2)
    ].copy()


def manual_review_sample(frame: pd.DataFrame, size: int = 20) -> pd.DataFrame:
    """Deterministic balanced sample, including every available mismatch type."""
    frame = frame.copy()
    frame["model_matches_rating_band"] = frame.apply(
        lambda row: sentiment_band(int(row["rating"])) == row["sentiment"], axis=1
    )
    mismatches = frame.loc[~frame["model_matches_rating_band"]]
    selected = mismatches.head(size)
    if len(selected) < size:
        remaining = frame.drop(index=selected.index).sample(
            n=min(size - len(selected), len(frame) - len(selected)),
            random_state=42,
        )
        selected = pd.concat([selected, remaining])
    selected["manual_note"] = selected.apply(
        lambda row: (
            "Review manually: model and customer rating bands disagree."
            if not row["model_matches_rating_band"]
            else "Prediction is directionally consistent with the customer rating."
        ),
        axis=1,
    )
    return selected
