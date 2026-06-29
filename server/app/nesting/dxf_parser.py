from dataclasses import dataclass
from typing import List

from ezdxf.document import Drawing
from shapely.geometry import Point, LineString, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.validation import make_valid


@dataclass(slots=True)
class DxfEntityGeometry:
    geometry: BaseGeometry
    handle: str


def _vec2(v):
    return Point(float(v[0]), float(v[1]))


def flatten_entity(entity, tol: float):
    h = entity.dxf.handle
    kind = entity.dxftype()

    if kind == "LINE":
        pts = [_vec2(entity.dxf.start), _vec2(entity.dxf.end)]

    elif kind == "LWPOLYLINE":
        pts = [_vec2(p) for p in entity.get_points(format="xy")]
        if entity.closed:
            pts.append(pts[0])

    elif kind == "POLYLINE":
        pts = [_vec2(p) for p in entity.points()]
        if getattr(entity, "is_closed", False):
            pts.append(pts[0])

    elif kind == "ARC":
        radius = entity.dxf.radius
        if radius < tol:
            pts = []
        else:
            pts = [_vec2(p) for p in entity.flattening(sagitta=tol)]

    elif kind == "CIRCLE":
        pts = [_vec2(p) for p in entity.flattening(sagitta=tol)]

    elif kind == "ELLIPSE":
        pts = [_vec2(p) for p in entity.flattening(distance=tol)]

    elif kind == "SPLINE":
        pts = [_vec2(p) for p in entity.flattening(distance=tol)]

    elif kind == "POINT":
        pts = [_vec2(entity.dxf.location)]

    else:
        raise Exception(f"Unsupported entity type: {kind} (handle: {h})")

    return pts, h


def convert_entity_to_shapely(entity, tol) -> DxfEntityGeometry | None:
    points = []
    points, h = flatten_entity(entity, tol)

    if len(points) == 0:
        return None

    if len(points) == 1:
        shapely_geom = Point(points[0])
    elif len(points) == 2:
        shapely_geom = LineString(points)
    else:
        first_point = points[0]
        last_point = points[-1]
        distance = first_point.distance(last_point)
        is_closed = distance < tol
        if is_closed:
            shapely_geom = Polygon(points)
        else:
            shapely_geom = LineString(points)

    return DxfEntityGeometry(geometry=shapely_geom, handle=h)
