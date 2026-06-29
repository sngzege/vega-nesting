import pytest
import io
import ezdxf
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.nesting.dxf_utils import read_dxf, read_dxf_file


def _make_simple_dxf():
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0))
    msp.add_line((10, 0), (10, 10))
    msp.add_line((10, 10), (0, 10))
    msp.add_line((0, 10), (0, 0))
    buf = io.StringIO()
    doc.write(buf)
    text = buf.getvalue()
    return text.encode("utf-8")


def test_read_dxf():
    buf = _make_simple_dxf()
    doc = read_dxf(buf)
    assert doc is not None
    msp = doc.modelspace()
    lines = list(msp.query("LINE"))
    assert len(lines) == 4
