import pytest
import ezdxf

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.nesting.build_geometry import build_geometry


def _make_simple_dxf():
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0))
    msp.add_line((10, 0), (10, 10))
    msp.add_line((10, 10), (0, 10))
    msp.add_line((0, 10), (0, 0))
    return doc


def test_build_geometry_simple():
    doc = _make_simple_dxf()
    polygons = build_geometry(doc, tolerance=0.1)
    assert len(polygons) >= 1
    assert polygons[0].geometry.area > 0
    assert len(polygons[0].handles) > 0
