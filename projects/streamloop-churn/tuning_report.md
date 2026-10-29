# StreamLoop churn tuning report

## Decision metric

Recall for churners is the primary search metric. A false negative means
StreamLoop misses a customer who is about to leave, which costs more than
sending a retention offer to a customer who would have stayed. Precision, F1,
accuracy, and ROC AUC are still reported so the recall gain is not considered
in isolation.

## Leakage controls

- The 7,043 rows were split into 5,634 training and
  1,409 test rows before fitting preprocessing or models.
- Imputation, scaling, and one-hot encoding live inside one `Pipeline`.
- Both searches used only the training split and five-fold stratified CV.
- The test set was evaluated once for the default baseline and once for the
  final refitted grid-search estimator.

## Baseline versus final test performance

| Model | Recall | Precision | F1 | Accuracy | ROC AUC |
| --- | ---: | ---: | ---: | ---: | ---: |
| Default baseline | 0.559 | 0.657 | 0.604 | 0.806 | 0.842 |
| Tuned final | 0.856 | 0.443 | 0.583 | 0.676 | 0.816 |

## Search and stability decision

`RandomizedSearchCV` first explored 24 combinations across five orders of
magnitude for C, both supported penalties, and optional class weighting. Its
best mean CV recall was 0.837. `GridSearchCV`
then refined around that C value. The selected configuration achieved mean CV
recall 0.837 with fold standard deviation
0.024. The top candidates were inspected by both mean
and standard deviation; the best-mean candidate was retained because its
variation was comparable with the nearby alternatives rather than an unstable
outlier.

Final hyperparameters:

```json
{
  "classifier__C": 0.003919406774847221,
  "classifier__class_weight": "balanced",
  "classifier__penalty": "l1",
  "classifier__solver": "liblinear"
}
```

The final model is the estimator automatically refitted by `GridSearchCV`; it
was not manually refit afterward.
