import tempfile
import ezdxf
from ezdxf.document import Drawing
from ezdxf import recover
from ezdxf.disassemble import recursive_decompose
from ezdxf.entities import DXFGraphic
from ezdxf.render.hatching import hatch_entity


def read_dxf(dxf_stream) -> Drawing:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as temp_file:
        if hasattr(dxf_stream, "read"):
            temp_file.write(dxf_stream.read())
        else:
            temp_file.write(dxf_stream)
        temp_file_path = temp_file.name
    return read_dxf_file(temp_file_path)


def read_dxf_file(dxf_path: str) -> Drawing | None:
    try:
        doc, auditor = recover.readfile(dxf_path)
    except Exception as e:
        print(f"Could not read DXF file: {dxf_path}, error: {e}")
        return None

    msp = doc.modelspace()

    text_entities = msp.query("TEXT MTEXT IMAGE SOLID")
    for text_entity in text_entities:
        msp.delete_entity(text_entity)

    new_doc = ezdxf.new()
    new_msp = new_doc.modelspace()

    flattened_entities = list(recursive_decompose(msp))
    for entity in flattened_entities:
        if isinstance(entity, DXFGraphic):
            new_entity = entity.copy()
            new_msp.add_entity(new_entity)

    hatches = new_msp.query("HATCH")
    for hatch in hatches:
        try:
            for line in hatch_entity(hatch):
                new_msp.add_line(line.start, line.end, dxfattribs=hatch.graphic_properties())
            new_msp.delete_entity(hatch)
        except Exception as e:
            print(f"Failed to convert HATCH: {e}")
            raise e

    return new_doc


def read_cleaned_dxf_file(dxf_path: str) -> Drawing | None:
    try:
        return ezdxf.readfile(dxf_path)
    except Exception as e:
        print(f"Could not read cleaned DXF: {dxf_path}, error: {e}")
        return None
