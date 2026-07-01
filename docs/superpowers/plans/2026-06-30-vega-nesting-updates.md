# Vega Nesting Güncellemeleri (2026-06-30)

> **For agentic workers:** Bu plan subagent-driven-development ile uygulanacaktır. Her task bağımsızdır ve aşağıdaki adımları takip eder.

**Goal:** Sac ölçülerini çerçeve olarak kullan, maks sac adedi girdisini kaldırıp otomatik hesaplama yap, malzeme bilgisi ekle, akıllı DXF çıktı isimlendirmesi ve ZIP indirmesi ekle

**Architecture:** Backend CRUD + dosya çözümleme + çıktı isimlendirme, frontend form + indirme UI, SQLite schema migration

**Tech Stack:** FastAPI, ezdxf, SQLite, Jinja2, Vanilla JS

---

## Task 1: Schema Migration + Database CRUD Güncelleme

**Files:**
- Modify: `server/app/database.py:18-84` (init_db migration)
- Modify: `server/app/database.py:147-199` (create_project)
- Modify: `server/app/database.py:202-261` (update_project)
- Modify: `server/app/database.py:264-312` (get_projects/get_project API response changes)
- Test: `server/tests/test_database.py`

**Step 1:** Write failing test for new schema columns

```python
def test_project_schema_has_new_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "test.db")
    db.init_db()
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(projects)")
    cols = {row["name"] for row in cursor.fetchall()}
    assert "sheet_material" in cols
    cursor.execute("PRAGMA table_info(project_files)")
    cols = {row["name"] for row in cursor.fetchall()}
    assert "material" in cols
    assert "thickness" in cols
    conn.close()
```

**Step 2:** Run test to verify it fails

```bash
cd server && pytest tests/test_database.py::test_project_schema_has_new_columns -v
```

**Step 3:** Implement schema migration + CRUD updates in `database.py`

Key changes:
- Add `sheet_material TEXT DEFAULT 'ST37'` to projects table with ALTER TABLE migration
- Add `material TEXT` and `thickness TEXT` to project_files with ALTER TABLE migration
- Add `output_names TEXT` to jobs table with ALTER TABLE migration
- Update `create_project` and `update_project` signatures to accept `sheet_material`
- Update `get_project` to return `sheet_material`, `material`, `thickness`

**Step 4:** Run tests to verify they pass

```bash
cd server && pytest tests/test_database.py -v
```

**Step 5:** Commit

```bash
git add server/app/database.py server/tests/test_database.py
git commit -m "feat: add sheet_material, material, thickness schema columns"
```

---

## Task 2: DXF İsim Çözümleme + Çıktı İsimlendirme Yardımcıları

**Files:**
- Create: `server/app/nesting/dxf_naming.py`
- Test: `server/tests/test_dxf_utils.py`

**Step 1:** Write failing tests

```python
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
```

**Step 2:** Run tests to verify they fail

```bash
cd server && pytest tests/test_dxf_utils.py::TestParseDxfFilename -v
```

**Step 3:** Implement `dxf_naming.py`

```python
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
        if info["material"] is None and token.upper() in KNOWN_MATERIALS:
            info["material"] = token
            idx += 1
            continue
        if info["thickness"] is None and UNIT_PATTERNS.match(token):
            info["thickness"] = token
            idx += 1
            continue
        break

    if idx < len(parts):
        last = parts[idx]
        m = re.search(r"(?:adet|ad\.?)(\d+)", last, re.IGNORECASE)
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
```

**Step 4:** Run tests to verify they pass

```bash
cd server && pytest tests/test_dxf_utils.py -v
```

**Step 5:** Commit

```bash
git add server/app/nesting/dxf_naming.py server/tests/test_dxf_utils.py
git commit -m "feat: add dxf filename parser and output naming helpers"
```

---

## Task 3: Sheet Frame (Çerçeve) Ekleme

**Files:**
- Modify: `server/app/nesting/engine.py:130-183` (build_part)
- Modify: `server/app/nesting/engine.py:185-214` (build_result_drawings)
- Modify: `server/app/nesting/engine.py:216-260` (nesting_process)

**Step 1:** Write failing test

```python
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
        drawings = build_result_drawings(file_entries, layouts, file_lookup, add_out_shape=True, space=0, sheet_width=1000, sheet_height=2000)
        assert len(drawings) == 1
        doc = drawings[0]
        has_frame = any(e.dxf.layer == "SHEET_FRAME" for e in doc.modelspace())
        assert has_frame
```

**Step 2:** Run test to verify it fails

```bash
cd server && pytest tests/test_build_geometry.py::TestSheetFrame -v
```

**Step 3:** Implement sheet frame in engine.py

Key changes:
- `build_part`: Add `sheet_width` and `sheet_height` parameters. If provided, add `SHEET_FRAME` layer with rectangle from (0,0) to (sheet_width, sheet_height)
- `build_result_drawings`: Pass `sheet_width` and `sheet_height` through to `build_part`
- `nesting_process`: Pass `sheet_width` and `sheet_height` to `build_result_drawings`

**Step 4:** Run tests to verify they pass

```bash
cd server && pytest tests/test_build_geometry.py::TestSheetFrame -v
```

**Step 5:** Commit

```bash
git add server/app/nesting/engine.py server/tests/test_build_geometry.py
git commit -m "feat: add sheet frame layer to output drawings"
```

---

## Task 4: Backend - sheetCount Kaldırma + Material Extraction + ZIP + Naming

**Files:**
- Modify: `server/app/main.py` (imports, POST/PUT /api/projects, POST /api/nest, process_job, status, new ZIP endpoint)

**Step 1:** Write failing tests

```python
def test_nest_without_sheetcount_with_material(client):
    buf = _make_simple_dxf()
    mock_output = {
        "solution": {
            "layouts": [
                {
                    "placed_items": [
                        {"item_id": 0, "transformation": {"rotation": 0.0, "translation": [0.0, 0.0]}},
                        {"item_id": 0, "transformation": {"rotation": 0.0, "translation": [10.0, 0.0]}},
                    ]
                }
            ]
        }
    }
    with patch("app.nesting.engine.run_lbf", return_value=mock_output):
        resp = client.post(
            "/api/nest",
            data={
                "sheetWidth": "100",
                "sheetHeight": "100",
                "space": "0",
                "sheetCount": "9999",
                "addOutShape": "false",
                "sheetMaterial": "ST52",
                "counts": "[2]",
                "rotations": "[]",
            },
            files=[
                ("files", ("partA-ST52-5mm-2adet.dxf", buf, "application/octet-stream")),
            ],
        )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    data = _wait_for_job(client, job_id)
    assert data["status"] == "done"
    assert data["stats"]["sheet_count"] == 1
    assert len(data["output_files"]) == 1
    fname = data["output_files"][0]
    resp = client.get(f"/api/result/{job_id}/{fname}")
    assert resp.status_code == 200
    resp = client.get(f"/api/result/{job_id}/all")
    assert resp.headers["content-type"] == "application/zip"

def test_project_saves_material(client):
    _login(client)
    buf = _make_simple_dxf()
    resp = client.post(
        "/api/projects",
        data={
            "name": "MatTest",
            "sheetWidth": "1000",
            "sheetHeight": "2000",
            "space": "1",
            "sheetCount": "9999",
            "addOutShape": "false",
            "sheetMaterial": "ALM",
            "counts": "[1]",
            "rotations": "[]",
        },
        files=[("files", ("part-ALM-3mm.dxf", buf, "application/octet-stream"))],
    )
    assert resp.status_code == 200
    pid = resp.json()["project_id"]
    resp = client.get(f"/api/projects/{pid}")
    proj = resp.json()
    assert proj["project"]["sheet_material"] == "ALM"
    assert proj["files"][0]["material"] == "ALM"
    assert proj["files"][0]["thickness"] == "3mm"
```

**Step 2:** Run tests to verify they fail

```bash
cd server && pytest tests/test_api.py::test_nest_without_sheetcount_with_material tests/test_api.py::test_project_saves_material -v
```

**Step 3:** Implement backend changes

Key changes in `main.py`:
1. Add imports: `from .nesting.dxf_naming import parse_dxf_filename, generate_default_output_name` and `import zipfile`, `from io import BytesIO`
2. `POST /api/projects` and `PUT /api/projects`: Remove `sheetCount` parameter, add `sheetMaterial: str = Form("ST37")`, add `fileMaterials` and `fileThicknesses` parsing, parse filenames for material/thickness, store overrides
3. `POST /api/nest`: Accept `sheetMaterial`, `fileMaterials`, `fileThicknesses`, apply overrides to file_entries
4. `process_job`: Save output with computed names using `generate_default_output_name`, store `output_names` in job
5. `GET /api/status/{job_id}`: Return `output_names`
6. New `GET /api/result/{job_id}/all`: Return ZIP of all output files

**Step 4:** Run tests to verify they pass

```bash
cd server && pytest tests/test_api.py -v
```

**Step 5:** Commit

```bash
git add server/app/main.py server/tests/test_api.py
git commit -m "feat: remove sheetCount input, add sheetMaterial, ZIP download, smart naming"
```

---

## Task 5: Frontend - Sheet Material + Per-File Info + ZIP Butonu

**Files:**
- Modify: `server/app/templates/index.html:30-78` (form inputs)
- Modify: `server/app/templates/index.html:248-259` (addRow)
- Modify: `server/app/templates/index.html:82-314` (JS form handling)
- Modify: `server/app/templates/index.html:396-468` (renderResults)

**Step 1 & 2:** Frontend changes (manual verification after implementation)

**Step 3:** Implement frontend changes

Key changes in `index.html`:
1. Replace "Maks. Sac Adedi" input with:
   - Hidden `sheetCount` input with value `9999`
   - New "Sac Malzemesi" input with datalist (ST37, ST52, ALM, 304)
2. Add per-file `material` and `thickness` inputs in file rows
3. Update JS form submission to collect material/thickness overrides and `sheetMaterial`
4. Update `loadProject` to load `sheet_material` and file fields
5. Update `renderResults`: show "Gereken Sac Adedi" instead of "Kullanılan sac", add "Tümünü İndir (ZIP)" button, implement `downloadAll` function

**Step 4:** Manual verification + run all tests

```bash
cd server && pytest tests/ -v
```

**Step 5:** Commit

```bash
git add server/app/templates/index.html server/app/static/style.css
git commit -m "feat: frontend sheet material, per-file overrides, ZIP download, calculated sheet count"
```

---

## Task 6: API Response Düzeltmeleri + loadProject Güncelleme

**Files:**
- Modify: `server/app/main.py:184-213` (GET /api/projects/{project_id})
- Modify: `server/app/templates/index.html:181-214` (loadProject JS)

**Step 1 & 2:** Minor changes, proceed to implementation

Key changes:
1. `GET /api/projects/{project_id}`: Ensure `sheet_material` is returned in project data, `material` and `thickness` in file data
2. `loadProject` JS: Load `sheet_material` into `#sheetMaterial` input

**Step 5:** Commit

```bash
git add server/app/main.py server/app/templates/index.html
git commit -m "fix: expose sheet_material and file fields in API and frontend load"
```

---

## Execution Order

1. Task 1 (Database schema + CRUD)
2. Task 2 (DXF naming helpers)
3. Task 3 (Sheet frame in engine)
4. Task 4 (Backend API changes)
5. Task 5 (Frontend changes)
6. Task 6 (API response + loadProject fixes)

Each task follows: implement -> test -> commit -> spec review -> code review -> mark complete.
