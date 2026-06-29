from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ezdxf.document import Drawing


def build_svg_string(drawing: "Drawing"):
    entities = drawing.modelspace()

    def _vec2(v):
        from shapely.geometry import Point

        return Point(float(v[0]), float(v[1]))

    flatten_entities = []
    for entity in entities:
        try:
            pts, _ = flatten_entity(entity, 0.1)
            flatten_entities.append(pts)
        except Exception:
            continue

    if not flatten_entities:
        return '<?xml version="1.0" encoding="utf-8"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'

    min_x = min(coord.x for flatten in flatten_entities for coord in flatten)
    min_y = min(coord.y for flatten in flatten_entities for coord in flatten)
    max_x = max(coord.x for flatten in flatten_entities for coord in flatten)
    max_y = max(coord.y for flatten in flatten_entities for coord in flatten)

    width = max_x - min_x
    height = max_y - min_y
    stroke_width = min(width, height) * 0.002

    parts = []
    parts.append('<?xml version="1.0" encoding="utf-8"?>')
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" viewBox="0 0 {width} {height}">')

    for flatten in flatten_entities:
        coords_str = " ".join([f"{coord.x - min_x} {coord.y - min_y}" for coord in flatten])
        parts.append(f'<path d="M {coords_str} Z" fill="none" stroke="#FF0000" stroke-width="{stroke_width}" />')

    parts.append("</svg>")
    return "\n".join(parts)


def flatten_entity(entity, tol: float):
    from shapely.geometry import Point

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


def create_svg_from_doc(doc: "Drawing", max_flattening_distance: float):
    return build_svg_string(doc)
