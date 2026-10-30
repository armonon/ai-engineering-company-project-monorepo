# Dogs vs. cats image classifier

This project follows the official 4Geeks image-classifier tutorial with a
memory-safe progressive input pipeline. It downloads the complete 25,000-image
training set, creates deterministic class-balanced train/validation/test
partitions, trains an EfficientNet-B0 classifier, evaluates the best checkpoint,
and saves the model locally.

```bash
cd projects/dogs-vs-cats
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python src/prepare_data.py
.venv/bin/python src/train.py
.venv/bin/pytest -q
```

The 581 MB archive and extracted third-party images remain ignored by Git. The
18 MB best Keras checkpoint is committed under `models/` because the assignment
explicitly requires the trained model in the corresponding folder. The
executed notebook and compact evaluation artifacts preserve the full training
and held-out-test evidence.
