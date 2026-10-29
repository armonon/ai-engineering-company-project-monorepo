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

The 581 MB archive, extracted images, and generated model are intentionally
ignored by Git, as the tutorial recommends. The executed notebook and compact
evaluation artifacts preserve reproducible evidence without committing model
weights or third-party image data.
