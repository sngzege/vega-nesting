import pytest
import io
import ezdxf
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.nesting.dxf_naming import parse_dxf_filename, generate_default_output_name
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


def test_generate_default_output_name_single_part():
    name = generate_default_output_name(
        unique_parts=1,
        part_name="DT000676_3_1",
        material="st37",
        thickness="3mm",
        part_quantity=1,
        sheet_material="ST37",
        sheet_width=3000,
        sheet_height=3000,
        sheet_count=4,
    )
    assert name == "DT000676_3_1-st37-1"


def test_generate_default_output_name_multi_part():
    name = generate_default_output_name(
        unique_parts=2,
        part_name="partA",
        material="st37",
        thickness="3mm",
        part_quantity=1,
        sheet_material="ST37",
        sheet_width=1500,
        sheet_height=3000,
        sheet_count=2,
    )
    assert name == "1500x3000-2-ST37"


class TestParseDxfFilename:
    def test_full_pattern(self):
        info = parse_dxf_filename("DT000676_3_1-st37-3mm-1adet.dxf")
        assert info["part_name"] == "DT000676_3_1"
        assert info["material"] == "st37"
        assert info["thickness"] == "3mm"
        assert info["count"] == 1

    def test_no_count(self):
        info = parse_dxf_filename("partA-ALM-5mm.dxf")
        assert info["part_name"] == "partA"
        assert info["material"] == "ALM"
        assert info["thickness"] == "5mm"
        assert info.get("count") is None

    def test_part_with_dash(self):
        info = parse_dxf_filename("part-1-ST52-2mm-10adet.dxf")
        assert info["part_name"] == "part-1"
        assert info["material"] == "ST52"
        assert info["thickness"] == "2mm"
        assert info["count"] == 10

    def test_no_material(self):
        info = parse_dxf_filename("myPart.dxf")
        assert info["part_name"] == "myPart"
        assert info.get("material") is None
        assert info.get("thickness") is None


class TestGenerateDefaultOutputName:
    def test_single_part(self):
        name = generate_default_output_name(
            unique_parts=1,
            part_name="DT000676_3_1",
            material="st37",
            thickness="3mm",
            part_quantity=1,
            sheet_material="ST37",
            sheet_width=3000,
            sheet_height=3000,
            sheet_count=4,
        )
        assert name == "DT000676_3_1-st37-1"

    def test_multi_part(self):
        name = generate_default_output_name(
            unique_parts=2,
            part_name="partA",
            material="st37",
            thickness="3mm",
            part_quantity=1,
            sheet_material="ST37",
            sheet_width=1500,
            sheet_height=3000,
            sheet_count=2,
        )
        assert name == "1500x3000-2-ST37"
