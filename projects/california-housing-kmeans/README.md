# California Housing K-means classification

This project completes the 4Geeks **K-means Project Tutorial** using the
official 20,640-row California Housing CSV. It uses only `Latitude`,
`Longitude`, and `MedInc`, as required.

## Reproduce the result

```bash
cd projects/california-housing-kmeans
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python src/train.py
.venv/bin/pytest -q
```

## Rubric map

| Assignment step | Evidence |
| --- | --- |
| Load `Latitude`, `Longitude`, `MedInc` and split train/test | `src/train.py::load_housing`, `split_housing`; disjoint deterministic split test |
| Train K-means with six clusters | Saved `models/kmeans_pipeline.joblib`; standardisation and `n_clusters=6` are one fitted pipeline |
| Store the cluster as a categorical column | `data/processed/train_clusters.csv` and `test_clusters.csv`; `label_frame` uses `pd.Categorical` |
| Plot the clusters and held-out predictions | `reports/figures/clusters_train_test.png` overlays held-out `x` markers on the learned geographic regions |
| Train and evaluate a supervised classifier | Saved `models/cluster_classifier.joblib`; `reports/metrics.json` includes accuracy, macro precision/recall/F1, per-class statistics, and confusion matrix |
| Save both models | Both fitted pipelines are versioned under `models/` and load-tested |

## Analysis

Standardisation is fitted only on the training partition because median income
and geographic coordinates have different units. The six clusters form
contiguous geographic/income regions rather than six simple latitude bands:
coastal metropolitan areas separate from inland and lower-income regions, and
the same location can change cluster as median income changes.

The fitted centres make the pattern concrete. Northern clusters 0 and 4 centre
near latitudes 38.34 and 37.70, while southern clusters 1 and 5 centre near
33.82 and 33.87. Income creates a second separation inside those broad regions:
clusters 0 and 1 centre around median incomes 2.84 and 2.80, while clusters 4
and 5 centre around 5.53 and 5.36. Cluster 2 is the smallest and highest-income
segment, centred at 10.55. These values are reported in original units under
`cluster_centres_original_units` in `reports/metrics.json`.

The held-out points occupy the same regions as the training points, supporting
that the K-means assignment is stable for unseen census-block groups. A Random
Forest is used for the supervised step because the six Voronoi-style regions
are non-linear in the original three-feature space. On the untouched 4,128-row
test set it reproduces the K-means labels with 99.35% accuracy and 99.11%
macro-F1. The confusion matrix quantifies that fidelity; it does not claim that
these automatically created labels are ground-truth housing categories.

## Leakage boundary

The train/test split is created before either model is fitted. K-means and its
scaler see training rows only. The classifier learns only the training labels
created by that fitted K-means pipeline, then is evaluated against K-means
predictions for the untouched test rows.
