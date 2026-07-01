import re
from typing import Optional, Dict, Any

KNOWN_MATERIALS = {"ST37", "ST52", "ALM", "304", "st37", "st52", "alm", "304"}
UNIT_PATTERNS = re.compile(r"^\d+(\.\d+)?(mm|cm|m|in)$")


def parse_dxf_filename(filename: str) -> Dict[str, Any]:
    base = filename.strip()
    if base.lower().endswith(".dxf"):
        base = base[:-4]
    if not base:
        return {"part_name": filename, "material": None, "thickness": None, "count": None}

    parts = base.split("-")
    info = {
        "part_name": parts[0],
        "material": None,
        "thickness": None,
        "count": None,
    }

    idx = 1
    while idx < len(parts):
        token = parts[idx]
        if token.upper() in KNOWN_MATERIALS:
            break
        if UNIT_PATTERNS.match(token):
            break
        idx += 1

    for i in range(1, idx):
        info["part_name"] += "-" + parts[i]

    if idx < len(parts):
        info["material"] = parts[idx]
        idx += 1
    if idx < len(parts) and UNIT_PATTERNS.match(parts[idx]):
        info["thickness"] = parts[idx]
        idx += 1
    if idx < len(parts):
        last = parts[idx]
        m = re.search(r"(\d+)(?:adet|ad\.?)", last, re.IGNORECASE)
        if m:
            try:
                info["count"] = int(m.group(1))
            except ValueError:
                pass
        else:
            try:
                info["count"] = int(last)
            except ValueError:
                pass

    return info


def generate_default_output_name(
    unique_parts: int,
    part_name: str,
    material: Optional[str],
    thickness: Optional[str],
    part_quantity: int,
    sheet_material: str,
    sheet_width: float,
    sheet_height: float,
    sheet_count: int,
) -> str:
    if unique_parts == 1:
        mat = material if material else sheet_material
        return f"{part_name}-{mat}-{part_quantity}"
    return f"{int(sheet_width)}x{int(sheet_height)}-{int(sheet_count)}-{sheet_material}"