"""Run pinned multilingual sentiment inference over all WeLoveReviews rows."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from analysis import predicted_stars, sentiment_band
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

MODEL_NAME = "nlptown/bert-base-multilingual-uncased-sentiment"
MODEL_REVISION = "8f6f4e3a8f70be4b65d3a4a8762b6d781cda240d"


def run(input_path: Path, output_path: Path) -> pd.DataFrame:
    frame = pd.read_csv(input_path)
    required = {"review_id", "rating", "review_text"}
    if set(frame.columns) != required:
        raise ValueError(f"expected exactly {sorted(required)}")
    if frame["review_text"].isna().any() or frame["review_text"].str.strip().eq("").any():
        raise ValueError("review_text contains missing or blank values")
    if not frame["rating"].between(1, 5).all():
        raise ValueError("rating must be between 1 and 5")

    # Load once, then batch all 500 rows. The immutable revision prevents a
    # future upstream model update from silently changing this analysis.
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, revision=MODEL_REVISION)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, revision=MODEL_REVISION
    )
    classifier = pipeline("text-classification", model=model, tokenizer=tokenizer, device=-1)
    predictions = classifier(
        frame["review_text"].tolist(),
        batch_size=16,
        truncation=True,
        max_length=512,
    )
    frame["predicted_stars"] = [predicted_stars(item["label"]) for item in predictions]
    frame["confidence"] = [round(float(item["score"]), 6) for item in predictions]
    frame["sentiment"] = frame["predicted_stars"].map(sentiment_band)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    return frame


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=root / "data/raw/reviews.csv")
    parser.add_argument(
        "--output", type=Path, default=root / "data/processed/reviews_with_sentiment.csv"
    )
    args = parser.parse_args()
    frame = run(args.input, args.output)
    print(f"processed={len(frame)} output={args.output}")


if __name__ == "__main__":
    main()
