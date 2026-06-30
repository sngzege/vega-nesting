# Output Preview & Naming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show inline SVG preview of each nesting result sheet and let user name output files before download.

**Architecture:** Add a lightweight SVG preview endpoint (`/api/preview/{job_id}/{sheet_index}`) that reads the generated DXF from `OUTPUT_DIR` and converts to SVG using existing `svg_generator.py`. Update the results UI to show previews + filename input. The download endpoint uses the user-specified name via query parameter.

**Tech Stack:** FastAPI, ezdxf, vanilla JS, existing svg_generator.py

## Global Constraints

- Use existing `svg_generator.create_svg_from_doc` for DXF→SVG conversion
- Preview must be fast: no re-processing, just read file and convert
- Output filename defaults to sheet name, user can override

---

### Task 1: SVG Preview API Endpoint

**Files:**
- Create: (none - use existing `svg_generator.py`)
- Modify: `server/app/main.py` (add endpoint)
- Test: `server/tests/test_api.py`

**Interfaces:**
- Consumes: `svg_generator.create_svg_from_doc(doc, max_flattening_distance=0.1)`, existing `OUTPUT_DIR` path, existing `JOBS` dict and `db.get_job_by_job_id`
- Produces: `GET /api/preview/{job_id}/{sheet_index}` returns `Response(content=svg_str, media_type="image/svg+xml")`

- [ ] **Step 1: Write failing tests**

Add to `server/tests/test_api.py`:

```python
def test_preview_endpoint(client):
    _login(client)
    buf = _make_simple_dxf()
    resp = client.post(
        "/api/nest",
        data={
            "sheetWidth": "100", "sheetHeight": "100", "space": "0",
            "sheetCount": "1", "addOutShape": "false",
            "counts": "[1]", "rotations": "[]",
        },
        files=[("files", ("test.dxf", buf, "application/octet-stream"))],
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    status_data = _wait_for_job(client, job_id)
    assert status_data["status"] == "done"

    # Preview first sheet
    resp = client.get(f"/api/preview/{job_id}/1")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/svg+xml"
    assert b"<svg" in resp.content

    # Preview invalid sheet
    resp = client.get(f"/api/preview/{job_id}/999")
    assert resp.status_code == 404

    # Preview invalid job
    resp = client.get("/api/preview/nonexistent/1")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/arge/vega-nesting/server && VEGA_TEST_MODE=1 ../venv/bin/python -m pytest tests/test_api.py::test_preview_endpoint -v
```

Expected: FAIL with 404 (endpoint doesn't exist yet).

- [ ] **Step 3: Add preview endpoint to main.py**

Add before the existing result endpoints in `server/app/main.py`:

```python
@app.get("/api/preview/{job_id}/{sheet_index}")
async def preview(job_id: str, sheet_index: int):
    if job_id not in JOBS:
        job = db.get_job_by_job_id(job_id)
        if not job or job["status"] != "done":
            raise HTTPException(status_code=404, detail="Job not found or not completed")
    else:
        job = JOBS[job_id]
        if job["status"] != "done":
            raise HTTPException(status_code=400, detail="Job not completed yet")

    output_files = job.get("output_files", [])
    if not output_files:
        raise HTTPException(status_code=404, detail="No output files")

    if sheet_index < 1 or sheet_index > len(output_files):
        raise HTTPException(status_code=404, detail=f"Sheet index out of range. Available: 1-{len(output_files)}")

    fname = output_files[sheet_index - 1]
    file_path = OUTPUT_DIR / fname
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File missing")

    doc = ezdxf.readfile(str(file_path))
    svg_str = create_svg_from_doc(doc, max_flattening_distance=0.1)
    return Response(content=svg_str, media_type="image/svg+xml")
```

Add import at top of `main.py`:
```python
from .nesting.svg_generator import create_svg_from_doc
import ezdxf
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/arge/vega-nesting/server && VEGA_TEST_MODE=1 ../venv/bin/python -m pytest tests/test_api.py::test_preview_endpoint -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/app/main.py server/tests/test_api.py
git commit -m "feat: add SVG preview endpoint for nesting results"
```

---

### Task 2: Custom Output Filename Support

**Files:**
- Modify: `server/app/main.py`
- Test: `server/tests/test_api.py`

**Interfaces:**
- Consumes: User-specified filename from query parameter `name` on download endpoint
- Produces: `Content-Disposition: attachment; filename="user-name_sheet_1.dxf"` headers

- [ ] **Step 1: Write failing tests**

```python
def test_result_with_custom_name(client):
    _login(client)
    buf = _make_simple_dxf()
    resp = client.post(
        "/api/nest",
        data={
            "sheetWidth": "100", "sheetHeight": "100", "space": "0",
            "sheetCount": "1", "addOutShape": "false",
            "counts": "[1]", "rotations": "[]",
        },
        files=[("files", ("test.dxf", buf, "application/octet-stream"))],
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    status_data = _wait_for_job(client, job_id)
    assert status_data["status"] == "done"

    # Single sheet - download with custom name
    resp = client.get(f"/api/result/{job_id}?name=ozel-cikti")
    assert resp.status_code == 200
    cd = resp.headers.get("content-disposition", "")
    assert "ozel-cikti.dxf" in cd

    # Multiple sheets scenario (test with query param on single download)
    resp = client.get(f"/api/result/{job_id}/{status_data['output_files'][0]}?name=parca-1")
    assert resp.status_code == 200
    cd = resp.headers.get("content-disposition", "")
    assert "parca-1.dxf" in cd
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/arge/vega-nesting/server && VEGA_TEST_MODE=1 ../venv/bin/python -m pytest tests/test_api.py::test_result_with_custom_name -v
```

Expected: FAIL (current implementation doesn't handle `name` query param).

- [ ] **Step 3: Update result endpoints**

In `server/app/main.py`, update both result endpoints to accept optional `name` query parameter:

```python
@app.get("/api/result/{job_id}/{filename}")
async def result(job_id: str, filename: str, name: Optional[str] = None):
    # ... existing validation ...
    download_name = name or filename
    if not download_name.endswith(".dxf"):
        download_name += ".dxf"
    return FileResponse(str(file_path), media_type="application/octet-stream", filename=download_name)


@app.get("/api/result/{job_id}")
async def result_all(job_id: str, name: Optional[str] = None):
    # ... existing validation ...
    if len(job["output_files"]) == 1:
        fname = job["output_files"][0]
        download_name = name or fname
        if not download_name.endswith(".dxf"):
            download_name += ".dxf"
        return FileResponse(str(OUTPUT_DIR / fname), media_type="application/octet-stream", filename=download_name)
    # Multiple sheets - redirect to individual downloads with naming
    raise HTTPException(status_code=400, detail="Multiple sheets available, download individually")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/arge/vega-nesting/server && VEGA_TEST_MODE=1 ../venv/bin/python -m pytest tests/test_api.py::test_result_with_custom_name -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/app/main.py server/tests/test_api.py
git commit -m "feat: support custom output filename via query parameter"
```

---

### Task 3: Frontend - Preview and Naming UI

**Files:**
- Modify: `server/app/templates/index.html`
- Modify: `server/app/static/style.css`

**Interfaces:**
- Consumes: `/api/preview/{job_id}/{sheet_index}` (returns SVG), `/api/result/{job_id}?name=...` and `/api/result/{job_id}/{filename}?name=...` (returns DXF with custom name)

- [ ] **Step 1: Update `renderResults` function**

Replace the existing `renderResults` function in `index.html`:

```javascript
function renderResults(jobId, data, container) {
    const stats = data.stats;
    const files = data.output_files || [];
    let html = `<div class="result-item success"><strong>Tamamlandı</strong><br>`;
    html += `İstenen: ${stats.requested} parça<br>`;
    html += `Yerleştirilen: ${stats.placed} parça<br>`;
    html += `Kullanılan sac: ${stats.sheet_count} adet<br>`;
    if (!stats.is_all_placed) {
        html += `<span style="color:#dc2626">Uyarı: Tüm parçalar yerleştirilemedi!</span>`;
    }
    html += `</div>`;

    // Output name input
    html += `<div class="result-item">`;
    html += `<label for="outputName" style="display:inline; margin-right:0.5rem;">Çıktı Adı:</label>`;
    html += `<input type="text" id="outputName" placeholder="vega-cikti" style="width:200px; padding:0.4rem;">`;
    html += `</div>`;

    // Preview + download per sheet
    files.forEach((f, idx) => {
        const sheetNum = idx + 1;
        html += `<div class="result-item preview-item">`;
        html += `<div class="preview-header">`;
        html += `<strong>Sac ${sheetNum}</strong>`;
        html += `</div>`;
        html += `<div class="preview-svg" id="preview-${jobId}-${sheetNum}">`;
        html += `<p>Önizleme yükleniyor...</p>`;
        html += `</div>`;
        html += `<div class="preview-download">`;
        html += `<button type="button" class="primary" onclick="downloadWithName('${jobId}', '${f}', ${sheetNum})">İndir (DXF)</button>`;
        html += `</div>`;
        html += `</div>`;
    });

    container.innerHTML = html;

    // Load previews
    files.forEach((f, idx) => {
        const sheetNum = idx + 1;
        fetch(`/api/preview/${jobId}/${sheetNum}`)
            .then(resp => {
                if (!resp.ok) throw new Error('Preview failed');
                return resp.text();
            })
            .then(svg => {
                const previewDiv = document.getElementById(`preview-${jobId}-${sheetNum}`);
                previewDiv.innerHTML = svg;
                const svgEl = previewDiv.querySelector('svg');
                if (svgEl) {
                    svgEl.style.width = '100%';
                    svgEl.style.maxHeight = '300px';
                    svgEl.style.background = '#fff';
                }
            })
            .catch(() => {
                const previewDiv = document.getElementById(`preview-${jobId}-${sheetNum}`);
                previewDiv.innerHTML = '<p style="color:#999;">Önizleme yüklenemedi</p>';
            });
    });
}
```

- [ ] **Step 2: Add download helper function**

Add to the JavaScript section (after `renderResults`):

```javascript
function downloadWithName(jobId, filename, sheetNum) {
    const nameInput = document.getElementById('outputName');
    const baseName = nameInput ? nameInput.value.trim() : '';
    const suffix = filename.replace(/\.dxf$/i, '');
    const downloadName = baseName ? `${baseName}_sac${sheetNum}` : suffix;
    const link = document.createElement('a');
    link.href = `/api/result/${jobId}/${filename}?name=${encodeURIComponent(downloadName)}`;
    link.download = downloadName + '.dxf';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
```

Also update the single-sheet download link in `renderResults` for multiple sheets case (in the `files.length === 1` branch):

```javascript
if (files.length === 1) {
    html += `<div class="result-item preview-item">`;
    html += `<div class="preview-header"><strong>Sac 1</strong></div>`;
    html += `<div class="preview-svg" id="preview-${jobId}-1"><p>Önizleme yükleniyor...</p></div>`;
    html += `<div class="preview-download">`;
    html += `<button type="button" class="primary" onclick="downloadWithName('${jobId}', '${files[0]}', 1)">İndir (DXF)</button>`;
    html += `</div></div>`;
} else {
    // ... (keep existing multi-file logic but use the preview pattern above)
}
```

Wait - simplify: remove the old `files.length === 1` special case and `else` block entirely, since the forEach loop above already handles both cases.

- [ ] **Step 3: Add CSS for preview**

Add to `server/app/static/style.css`:

```css
.preview-item {
    padding: 1rem;
}
.preview-header {
    margin-bottom: 0.5rem;
}
.preview-svg {
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 0.5rem;
    margin-bottom: 0.5rem;
    background: #fff;
    overflow: hidden;
}
.preview-svg svg {
    display: block;
    margin: 0 auto;
}
.preview-download {
    text-align: right;
}
```

- [ ] **Step 4: Restart service and test manually**

```bash
echo 'Vega!12345' | sudo -S systemctl restart vega-nesting
```

Then open browser to `http://192.168.2.200:8000`, log in, upload a DXF, run nesting, verify:
- Preview SVG loads for each sheet
- Default filename in input
- Changing the name and clicking download uses the custom name

- [ ] **Step 5: Run existing tests to verify no regressions**

```bash
cd /home/arge/vega-nesting/server && VEGA_TEST_MODE=1 ../venv/bin/python -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add server/app/templates/index.html server/app/static/style.css
git commit -m "feat: add SVG preview and custom output naming in UI"
```
