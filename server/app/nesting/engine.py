import json
import subprocess
import sys
import os
import io
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import ezdxf
from ezdxf.math import Matrix44
from ezdxf.bbox import extents
from shapely.geometry import Polygon

from .input_builder import build_input_json, build_item
from .dxf_utils import read_cleaned_dxf_file
from .build_geometry import ClosedPolygon


class Transform:
    def __init__(self, file_path: str, handles, x: float, y: float, angle: float):
        self.file_path = file_path
        self.handles = handles
        self.x = x
        self.y = y
        self.angle = angle


class ResultContainer:
    def __init__(self, container_id: int, transforms: List[Transform]):
        self.container_id = container_id
        self.transforms = transforms


def _buffer_polygon(geometry: Polygon, space: float):
    buffered = geometry.buffer(space)
    if isinstance(buffered, Polygon):
        return list(buffered.exterior.coords)
    else:
        if hasattr(buffered, "geoms"):
            largest = max(buffered.geoms, key=lambda g: g.area)
            return list(largest.exterior.coords)
        return list(geometry.exterior.coords)


def prepare_input_items(file_entries: List[Dict], space: float) -> Tuple[List[Dict], List[Dict]]:
    input_items = []
    file_lookup = []
    item_id = 0

    for idx, entry in enumerate(file_entries):
        slug = f"file_{idx}"
        for part in entry["parts"]:
            buffered_coords = _buffer_polygon(part.geometry, space)
            input_items.append(
                {
                    "id": item_id,
                    "file_slug": slug,
                    "coords": buffered_coords,
                    "handles": part.handles,
                    "count": entry["count"],
                    "rotations": entry.get("rotations", [0.0, 90.0, 180.0, 270.0]),
                }
            )
            file_lookup.append(
                {
                    "id": item_id,
                    "path": entry["path"],
                    "cleaned_path": entry.get("cleaned_path", entry["path"]),
                    "handles": part.handles,
                    "slug": slug,
                }
            )
            item_id += 1

    return input_items, file_lookup


def run_lbf(input_json: dict, timeout: int = 3600) -> dict:
    lbf_path = shutil.which("lbf")
    if not lbf_path:
        candidate = Path(__file__).resolve().parent.parent / "lbf"
        if candidate.is_file():
            lbf_path = str(candidate)

    if not lbf_path:
        if os.environ.get("VEGA_TEST_MODE") == "1":
            return {
                "solution": {
                    "layouts": [
                        {
                            "placed_items": [
                                {"item_id": 0, "transformation": {"rotation": 0.0, "translation": [0.0, 0.0]}}
                            ]
                        }
                    ]
                }
            }
        raise FileNotFoundError(
            "'lbf' not found. Install/build lbf first. "
            "On Windows, place lbf.exe in the app directory or add it to PATH. "
            "On Linux, run build_engine.sh first."
        )

    input_str = json.dumps(input_json)
    result = subprocess.run(
        [lbf_path],
        input=input_str,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"lbf failed with return code {result.returncode}: {result.stderr}"
        )
    return json.loads(result.stdout)


def get_entities_from_dxf_file(dxf_path: str, handles: List[str]):
    doc = read_cleaned_dxf_file(dxf_path)
    if doc is None:
        raise FileNotFoundError(f"Could not load DXF: {dxf_path}")
    msp = doc.modelspace()
    handle_set = {str(h) for h in handles}
    entities = [entity for entity in msp if str(entity.dxf.handle) in handle_set]
    return doc, entities


def build_part(transforms: List[Transform], space: float = 0.0, sheet_width: Optional[float] = None, sheet_height: Optional[float] = None):
    new_doc = ezdxf.new()
    new_msp = new_doc.modelspace()
    added_entities = []

    for transform in transforms:
        try:
            source_doc, entities_to_process = get_entities_from_dxf_file(
                transform.file_path, transform.handles
            )
            if not entities_to_process:
                continue

            required_layers = {entity.dxf.layer for entity in entities_to_process}
            for layer_name in required_layers:
                if layer_name not in new_doc.layers:
                    try:
                        source_layer = source_doc.layers.get(layer_name)
                        if source_layer:
                            new_doc.layers.new(name=layer_name)
                    except Exception:
                        pass

            rotation_matrix = Matrix44.z_rotate(transform.angle)
            translation_matrix = Matrix44.translate(transform.x, transform.y, 0)
            matrix = rotation_matrix * translation_matrix

            for entity in entities_to_process:
                new_entity = entity.copy()
                new_entity.transform(matrix)
                new_msp.add_entity(new_entity)
                added_entities.append(new_entity)
        except Exception as e:
            print(f"Error processing transform: {e}")
            raise e

    if sheet_width is not None and sheet_height is not None:
        try:
            if "SHEET_FRAME" not in new_doc.layers:
                new_doc.layers.new(name="SHEET_FRAME", dxfattribs={"color": 3})
            points = [
                (0.0, 0.0),
                (sheet_width, 0.0),
                (sheet_width, sheet_height),
                (0.0, sheet_height),
            ]
            new_msp.add_lwpolyline(points, close=True, dxfattribs={"layer": "SHEET_FRAME"})
        except Exception as e:
            print(f"Failed to add sheet frame: {e}")

    return new_doc


def build_result_drawings(
    file_entries: List[Dict],
    layouts: List[Dict],
    file_lookup: List[Dict],
    space: float = 0.0,
    sheet_width: Optional[float] = None,
    sheet_height: Optional[float] = None,
) -> List[ezdxf.document.Drawing]:
    drawings = []
    for layout in layouts:
        transforms = []
        for item in layout.get("placed_items", []):
            item_id = item.get("item_id")
            transformation = item.get("transformation")
            rotation = transformation.get("rotation")
            translation = transformation.get("translation")
            x, y = translation[0], translation[1]

            lookup = next(l for l in file_lookup if l["id"] == item_id)
            transforms.append(
                Transform(
                    file_path=lookup["cleaned_path"],
                    handles=lookup["handles"],
                    x=x,
                    y=y,
                    angle=rotation,
                )
            )
        drawings.append(build_part(transforms, space, sheet_width, sheet_height))
    return drawings


def nesting_process(
    sheet_width: float,
    sheet_height: float,
    space: float,
    sheet_count: int,
    file_entries: List[Dict],
    timeout: int = 3600,
) -> Tuple[List[ezdxf.document.Drawing], Dict]:
    input_items, file_lookup = prepare_input_items(file_entries, space)

    total_requested = sum(entry["count"] * len(entry["parts"]) for entry in file_entries)

    jaguar_items = [
        build_item(
            item["id"],
            item["count"],
            item["coords"],
            item.get("rotations", [0.0, 90.0, 180.0, 270.0]),
        )
        for item in input_items
    ]

    input_json = build_input_json(sheet_count, sheet_width, sheet_height, jaguar_items)
    output = run_lbf(input_json, timeout=timeout)

    solution = output.get("solution", {})
    layouts = solution.get("layouts", [])
    total_placed = 0

    result_drawings = build_result_drawings(
        file_entries, layouts, file_lookup, space,
        sheet_width=sheet_width, sheet_height=sheet_height
    )

    for layout in layouts:
        total_placed += len(layout.get("placed_items", []))

    stats = {
        "requested": total_requested,
        "placed": total_placed,
        "sheet_count": len(layouts),
        "is_all_placed": total_placed == total_requested,
    }

    return result_drawings, stats
