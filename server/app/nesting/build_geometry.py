from dataclasses import dataclass
from typing import List

from .dxf_parser import DxfEntityGeometry, convert_entity_to_shapely
from ezdxf.document import Drawing
from shapely.geometry import Polygon
from shapely.validation import make_valid
from shapely.ops import unary_union


@dataclass(slots=True)
class ClosedPolygon:
    geometry: Polygon
    handles: List[str]


def merge_dxf_entities_into_polygons(dxf_entities, tolerance: float) -> List[ClosedPolygon]:
    result = []
    for dxf_entity in dxf_entities:
        shapelly_geom = dxf_entity.geometry.convex_hull.buffer(tolerance)
        area = shapelly_geom.area
        if area > 1e-10:
            result.append(ClosedPolygon(geometry=make_valid(shapelly_geom), handles=[dxf_entity.handle]))

    while True:
        old_size = len(result)
        result.sort(key=lambda cp: cp.geometry.area, reverse=True)
        for i in range(len(result)):
            to_remove = []
            is_found = False
            for j in range(i + 1, len(result)):
                if result[i].geometry.intersects(result[j].geometry):
                    result[i].geometry = result[i].geometry.union(result[j].geometry).convex_hull
                    result[i].handles.extend(result[j].handles)
                    to_remove.append(j)
                    is_found = True
            if is_found:
                for j in sorted(to_remove, reverse=True):
                    result.pop(j)
                break

        if old_size == len(result):
            break

    return result


def build_geometry(drawing: Drawing, tolerance: float) -> List[ClosedPolygon]:
    msp = drawing.modelspace()

    dxf_geometries: List[DxfEntityGeometry] = []
    for entity in msp:
        try:
            dxf_geometry: DxfEntityGeometry | None = convert_entity_to_shapely(entity, tolerance)
            if dxf_geometry is not None:
                dxf_geometries.append(dxf_geometry)
        except Exception as e:
            print(f"Error converting entity {entity.dxftype()} handle {entity.dxf.handle}: {e}")
            raise e

    closed_polygons = merge_dxf_entities_into_polygons(dxf_geometries, tolerance)
    return closed_polygons
