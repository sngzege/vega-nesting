import pytest
import ezdxf

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.nesting.build_geometry import build_geometry
from app.nesting.engine import build_result_drawings


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


class TestSheetFrame:
    def test_sheet_frame_added_to_output(self):
        file_entries = [{
            "path": "dummy.dxf",
            "cleaned_path": "dummy.dxf",
            "parts": [],
            "count": 1,
            "rotations": [0.0],
        }]
        layouts = [{"placed_items": []}]
        file_lookup = [{"id": 0, "path": "dummy.dxf", "cleaned_path": "dummy.dxf", "handles": [], "slug": "f0"}]
        drawings = build_result_drawings(file_entries, layouts, file_lookup, space=0, sheet_width=1000, sheet_height=2000)
        assert len(drawings) == 1
        doc = drawings[0]
        has_frame = any(e.dxf.layer == "SHEET_FRAME" for e in doc.modelspace())
        assert has_frame
