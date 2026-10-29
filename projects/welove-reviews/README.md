# WeLoveReviews sentiment analysis

This project integrates the required pinned
`nlptown/bert-base-multilingual-uncased-sentiment` model over all 500 service
reviews. The executed notebook is the client-facing narrative; `src/app.py` is
the reproducible production inference path.

```bash
cd projects/welove-reviews
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python src/app.py
.venv/bin/pytest -q
```

The model is deliberately evaluated for service-review domain mismatch. High
human ratings classified as one or two stars are retained and analyzed rather
than corrected or hidden.
