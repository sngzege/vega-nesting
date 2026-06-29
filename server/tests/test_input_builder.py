import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.nesting.input_builder import build_input_json, build_item


def test_build_item():
    item = build_item(0, 1, [[0, 0], [10, 0], [10, 10], [0, 10]], [0, 90])
    assert item["id"] == 0
    assert item["demand"] == 1
    assert item["shape"]["type"] == "simple_polygon"
    assert item["shape"]["data"] == [[0, 0], [10, 0], [10, 10], [0, 10]]


def test_build_input_json():
    items = [build_item(0, 1, [[0, 0], [10, 0], [10, 10], [0, 10]], [0])]
    data = build_input_json(1, 100, 100, items)
    assert data["problem_type"] == "bpp"
    assert len(data["instance"]["items"]) == 1
    assert len(data["instance"]["bins"]) == 1
    assert data["instance"]["bins"][0]["shape"]["data"]["outer"] == [
        [0.0, 0.0],
        [100.0, 0.0],
        [100.0, 100.0],
        [0.0, 100.0],
        [0.0, 0.0],
    ]
