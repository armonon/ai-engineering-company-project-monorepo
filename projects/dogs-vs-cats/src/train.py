"""Train and evaluate an EfficientNet-B0 dogs-vs-cats classifier."""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.metrics import classification_report, confusion_matrix
from tensorflow import keras

IMAGE_SIZE = (200, 200)
BATCH_SIZE = 32
SEED = 42


def set_determinism() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    tf.random.set_seed(SEED)


def load_datasets(root: Path) -> tuple[tf.data.Dataset, tf.data.Dataset, tf.data.Dataset]:
    common = {
        "labels": "inferred",
        "label_mode": "categorical",
        "class_names": ["cat", "dog"],
        "image_size": IMAGE_SIZE,
        "batch_size": BATCH_SIZE,
        "seed": SEED,
    }
    processed = root / "data" / "processed"
    train = keras.utils.image_dataset_from_directory(
        processed / "train", shuffle=True, **common
    )
    validation = keras.utils.image_dataset_from_directory(
        processed / "validation", shuffle=False, **common
    )
    test = keras.utils.image_dataset_from_directory(
        processed / "test", shuffle=False, **common
    )
    autotune = tf.data.AUTOTUNE
    return (
        train.prefetch(autotune),
        validation.prefetch(autotune),
        test.prefetch(autotune),
    )


def build_model() -> keras.Model:
    augmentation = keras.Sequential(
        [keras.layers.RandomFlip("horizontal"), keras.layers.RandomRotation(0.05)],
        name="augmentation",
    )
    backbone = keras.applications.EfficientNetB0(
        include_top=False,
        weights="imagenet",
        input_shape=(*IMAGE_SIZE, 3),
    )
    backbone.trainable = False
    inputs = keras.Input(shape=(*IMAGE_SIZE, 3))
    features = backbone(augmentation(inputs), training=False)
    features = keras.layers.GlobalAveragePooling2D()(features)
    features = keras.layers.Dropout(0.25)(features)
    features = keras.layers.Dense(128, activation="relu")(features)
    outputs = keras.layers.Dense(2, activation="softmax")(features)
    model = keras.Model(inputs, outputs, name="dogs_vs_cats_efficientnet_b0")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def train_and_evaluate(root: Path, epochs: int = 5) -> dict[str, object]:
    set_determinism()
    train, validation, test = load_datasets(root)
    model = build_model()
    models = root / "models"
    artifacts = root / "artifacts"
    models.mkdir(exist_ok=True)
    artifacts.mkdir(exist_ok=True)
    checkpoint = models / "efficientnet_b0_best.keras"
    callbacks = [
        keras.callbacks.ModelCheckpoint(
            checkpoint, monitor="val_accuracy", mode="max", save_best_only=True
        ),
        keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=2, restore_best_weights=True
        ),
    ]
    history = model.fit(
        train,
        validation_data=validation,
        epochs=epochs,
        callbacks=callbacks,
        verbose=2,
    )
    pd.DataFrame(history.history).to_csv(artifacts / "history.csv", index=False)

    best = keras.models.load_model(checkpoint)
    test_loss, test_accuracy = best.evaluate(test, verbose=0)
    probabilities = best.predict(test, verbose=0)
    predictions = probabilities.argmax(axis=1)
    labels = np.concatenate([batch_labels.numpy().argmax(axis=1) for _, batch_labels in test])
    report = classification_report(
        labels, predictions, target_names=["cat", "dog"], output_dict=True
    )
    matrix = confusion_matrix(labels, predictions).tolist()
    results = {
        "architecture": "EfficientNetB0",
        "image_size": list(IMAGE_SIZE),
        "epochs_completed": len(history.history["loss"]),
        "test_loss": float(test_loss),
        "test_accuracy": float(test_accuracy),
        "confusion_matrix": matrix,
        "classification_report": report,
        "checkpoint": "models/efficientnet_b0_best.keras (generated locally, gitignored)",
    }
    (artifacts / "evaluation.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    return results


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(train_and_evaluate(root), indent=2))


if __name__ == "__main__":
    main()
