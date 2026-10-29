# StreamLoop churn tuning

This project compares a default logistic-regression baseline with a two-stage
hyperparameter search. Recall is the primary metric because StreamLoop loses
more from a missed churner than from an unnecessary retention offer.

```bash
cd projects/streamloop-churn
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python src/train.py
.venv/bin/pytest -q
```

The executed notebook documents the complete experiment. Preprocessing is
inside the scikit-learn pipeline, both searches see only the training split,
and the test split is evaluated only for the default baseline and final model.
