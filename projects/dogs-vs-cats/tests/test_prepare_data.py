import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from prepare_data import partition_for_index


@pytest.mark.parametrize(
    ("index", "expected"),
    [(0, "train"), (8_749, "train"), (8_750, "validation"), (10_624, "validation"), (10_625, "test"), (12_499, "test")],
)
def test_partition_boundaries(index, expected):
    assert partition_for_index(index) == expected


def test_out_of_range_index_is_rejected():
    with pytest.raises(ValueError):
        partition_for_index(12_500)
