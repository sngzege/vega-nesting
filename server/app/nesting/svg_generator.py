from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ezdxf.document import Drawing

OUT_SHAPE_COLOR = "#CC5500"
PART_COLOR = "#000000"


def build_svg_string(
    drawing: "Drawing",
    sheet_width: Optional[float] = None,
    sheet_height: Optional[float] = None,
):
    entities = drawing.modelspace()

    flattened = []
    for entity in entities:
        try:
            pts, _, layer = flatten_entity(entity, 0.1)
            if not pts:
                continue
            layer_name = layer if layer else ""
            flattened.append((pts, layer_name))
        except Exception:
            continue

    if not flattened:
        return '<?xml version="1.0" encoding="utf-8"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'

    all_pts = [pt for pts, _ in flattened for pt in pts]

    if sheet_width and sheet_height:
        vb_w = sheet_width
        vb_h = sheet_height
    else:
        min_x = min(p.x for p in all_pts)
        min_y = min(p.y for p in all_pts)
        max_x = max(p.x for p in all_pts)
        max_y = max(p.y for p in all_pts)
        vb_w = max_x - min_x
        vb_h = max_y - min_y

    stroke_w = min(vb_w, vb_h) * 0.002

    parts = []
    parts.append('<?xml version="1.0" encoding="utf-8"?>')
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{vb_w}mm" height="{vb_h}mm" viewBox="0 0 {vb_w} {vb_h}">'
    )

    for pts, layer_name in flattened:
        color = OUT_SHAPE_COLOR if layer_name == "OUT_SHAPE" else PART_COLOR
        coords = " ".join(f"{p.x} {p.y}" for p in pts)
        parts.append(
            f'<path d="M {coords} Z" fill="none" stroke="{color}" stroke-width="{stroke_w}" />'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def flatten_entity(entity, tol: float):
    from shapely.geometry import Point

    def _vec2(v):
        return Point(float(v[0]), float(v[1]))

    h = entity.dxf.handle
    layer = entity.dxf.layer
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

    return pts, h, layer


def create_svg_from_doc(
    doc: "Drawing",
    max_flattening_distance: float,
    sheet_width: Optional[float] = None,
    sheet_height: Optional[float] = None,
):
    return build_svg_string(doc, sheet_width=sheet_width, sheet_height=sheet_height)
