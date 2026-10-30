"""Download and deterministically partition the official dogs-vs-cats data."""

from __future__ import annotations

import argparse
import shutil
import urllib.request
import zipfile
from pathlib import Path

DATA_URL = "https://storage.googleapis.com/datascience-materials/dogs-vs-cats.zip"
EXPECTED_PER_CLASS = 12_500
BOUNDARIES = {
    "train": range(0, 8_750),
    "validation": range(8_750, 10_625),
    "test": range(10_625, 12_500),
}


def partition_for_index(index: int) -> str:
    for partition, indices in BOUNDARIES.items():
        if index in indices:
            return partition
    raise ValueError(f"image index outside expected range: {index}")


def prepare(root: Path, force: bool = False) -> dict[str, int]:
    archive = root / "data" / "dogs-vs-cats.zip"
    processed = root / "data" / "processed"
    complete = processed / ".complete"
    if complete.exists() and not force:
        return count_images(processed)
    if force and processed.exists():
        shutil.rmtree(processed)

    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        urllib.request.urlretrieve(DATA_URL, archive)
    for partition in BOUNDARIES:
        for label in ("cat", "dog"):
            (processed / partition / label).mkdir(parents=True, exist_ok=True)

    seen = {"cat": 0, "dog": 0}
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            filename = Path(member.filename).name
            if not (filename.startswith(("cat.", "dog.")) and filename.endswith(".jpg")):
                continue
            label, index_text, _ = filename.split(".")
            index = int(index_text)
            partition = partition_for_index(index)
            destination = processed / partition / label / filename
            with bundle.open(member) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
            seen[label] += 1

    if seen != {"cat": EXPECTED_PER_CLASS, "dog": EXPECTED_PER_CLASS}:
        raise RuntimeError(f"expected 12,500 images per class, found {seen}")
    complete.write_text("25,000 images partitioned deterministically\n", encoding="utf-8")
    return count_images(processed)


def count_images(processed: Path) -> dict[str, int]:
    return {
        partition: sum(1 for _ in (processed / partition).glob("*/*.jpg"))
        for partition in BOUNDARIES
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    print(prepare(root, force=args.force))


if __name__ == "__main__":
    main()
