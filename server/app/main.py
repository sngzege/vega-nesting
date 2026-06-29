import os
import uuid
import shutil
import json
from io import StringIO
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import database as db
from .nesting.dxf_utils import read_dxf
from .nesting.build_geometry import build_geometry
from .nesting.engine import nesting_process
from .nesting.input_builder import build_item

app = FastAPI(title="Vega Nesting")

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"

for d in [UPLOAD_DIR, OUTPUT_DIR]:
    d.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

db.init_db()

JOBS = {}


@app.middleware("http")
async def session_middleware(request: Request, call_next):
    session_id = request.cookies.get("session_id")
    request.state.session = None
    request.state.user = None
    if session_id:
        session = db.get_session(session_id)
        if session:
            request.state.session = session
            request.state.user = {"id": session["user_id"], "username": session["username"]}
    response = await call_next(request)
    return response


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    session = request.state.session
    user = request.state.user
    projects = []
    if session:
        projects = db.get_projects(session["session_id"])
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user,
            "projects": projects,
        },
    )


@app.post("/api/login")
async def login(request: Request, response: Response, username: str = Form(...)):
    username = username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username required")
    user_id = db.get_or_create_user(username)
    session_id = db.create_session(user_id)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=False,
        max_age=60 * 60 * 24 * 30,
    )
    return {"username": username}


@app.post("/api/logout")
async def logout(request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    if session_id:
        db.delete_session(session_id)
    response.delete_cookie("session_id")
    return {"ok": True}


@app.get("/api/me")
async def me(request: Request):
    session = request.state.session
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"username": session["username"]}


# Projects


@app.get("/api/projects")
async def list_projects(request: Request):
    session = request.state.session
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    projects = db.get_projects(session["session_id"])
    return projects


@app.post("/api/projects")
async def create_project(
    request: Request,
    name: str = Form(...),
    sheetWidth: float = Form(...),
    sheetHeight: float = Form(...),
    space: float = Form(...),
    sheetCount: int = Form(1),
    addOutShape: bool = Form(False),
    files: List[UploadFile] = File(...),
    counts: str = Form(...),
    rotations: str = Form(default="[]"),
):
    session = request.state.session
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        counts_list = json.loads(counts)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid counts JSON")

    try:
        rotations_list = json.loads(rotations)
    except Exception:
        rotations_list = [[] for _ in files]

    if len(counts_list) != len(files):
        raise HTTPException(status_code=400, detail="Length of counts must match number of files")
    if len(rotations_list) != len(files):
        rotations_list = [[] for _ in files]

    saved_files = []
    for idx, upload in enumerate(files):
        original_bytes = await upload.read()
        drawing = read_dxf(original_bytes)
        if drawing is None:
            raise HTTPException(status_code=400, detail=f"Could not parse DXF: {upload.filename}")

        buf = StringIO()
        drawing.write(buf)
        cleaned_bytes = buf.getvalue().encode("utf-8")

        saved_files.append(
            {
                "filename": upload.filename,
                "original_content": original_bytes,
                "cleaned_content": cleaned_bytes,
                "count": counts_list[idx],
                "rotations": rotations_list[idx] if rotations_list[idx] else [0.0, 90.0, 180.0, 270.0],
            }
        )

    project_id = db.create_project(
        session_id=session["session_id"],
        name=name,
        sheet_width=sheetWidth,
        sheet_height=sheetHeight,
        space=space,
        sheet_count=sheetCount,
        add_out_shape=addOutShape,
        files=saved_files,
    )

    return {"project_id": project_id}


@app.get("/api/projects/{project_id}")
async def get_project_api(request: Request, project_id: int):
    session = request.state.session
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    data = db.get_project(session["session_id"], project_id)
    if not data:
        raise HTTPException(status_code=404, detail="Project not found")
    # Convert rotations back to list; filenames only (no bytes)
    return {
        "project": {
            "id": data["project"]["id"],
            "name": data["project"]["name"],
            "sheet_width": data["project"]["sheet_width"],
            "sheet_height": data["project"]["sheet_height"],
            "space": data["project"]["space"],
            "sheet_count": data["project"]["sheet_count"],
            "add_out_shape": bool(data["project"]["add_out_shape"]),
            "created_at": data["project"]["created_at"],
            "updated_at": data["project"]["updated_at"],
        },
        "files": [
            {
                "filename": f["filename"],
                "count": f["count"],
                "rotations": json.loads(f["rotations"]) if f["rotations"] else [0.0, 90.0, 180.0, 270.0],
            }
            for f in data["files"]
        ],
    }


@app.delete("/api/projects/{project_id}")
async def delete_project_api(request: Request, project_id: int):
    session = request.state.session
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not db.delete_project(session["session_id"], project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True}


@app.put("/api/projects/{project_id}")
async def update_project_api(
    request: Request,
    project_id: int,
    name: str = Form(...),
    sheetWidth: float = Form(...),
    sheetHeight: float = Form(...),
    space: float = Form(...),
    sheetCount: int = Form(1),
    addOutShape: bool = Form(False),
    files: List[UploadFile] = File(default=[]),
    counts: str = Form(...),
    rotations: str = Form(default="[]"),
):
    session = request.state.session
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        counts_list = json.loads(counts)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid counts JSON")

    try:
        rotations_list = json.loads(rotations)
    except Exception:
        rotations_list = [[] for _ in files]

    if len(counts_list) != len(files):
        raise HTTPException(status_code=400, detail="Length of counts must match number of files")
    if len(rotations_list) != len(files):
        rotations_list = [[] for _ in files]

    saved_files = []
    for idx, upload in enumerate(files):
        original_bytes = await upload.read()
        drawing = read_dxf(original_bytes)
        if drawing is None:
            raise HTTPException(status_code=400, detail=f"Could not parse DXF: {upload.filename}")

        buf = StringIO()
        drawing.write(buf)
        cleaned_bytes = buf.getvalue().encode("utf-8")

        saved_files.append(
            {
                "filename": upload.filename,
                "original_content": original_bytes,
                "cleaned_content": cleaned_bytes,
                "count": counts_list[idx],
                "rotations": rotations_list[idx] if rotations_list[idx] else [0.0, 90.0, 180.0, 270.0],
            }
        )

    if not db.update_project(
        project_id,
        session["session_id"],
        name,
        sheetWidth,
        sheetHeight,
        space,
        sheetCount,
        addOutShape,
        saved_files,
    ):
        raise HTTPException(status_code=404, detail="Project not found")

    return {"project_id": project_id}


def process_job(
    job_id: str,
    sheet_width: float,
    sheet_height: float,
    space: float,
    sheet_count: int,
    add_out_shape: bool,
    file_entries: List[dict],
    project_id: Optional[int] = None,
):
    JOBS[job_id]["status"] = "processing"
    db.update_job(
        job_id,
        status="processing",
        started_at=datetime.now().isoformat(),
    )
    try:
        drawings, stats = nesting_process(
            sheet_width=sheet_width,
            sheet_height=sheet_height,
            space=space,
            sheet_count=sheet_count,
            add_out_shape=add_out_shape,
            file_entries=file_entries,
            timeout=3600,
        )
        output_files = []
        for idx, drawing in enumerate(drawings, start=1):
            out_path = OUTPUT_DIR / f"{job_id}_sheet_{idx}.dxf"
            drawing.saveas(str(out_path))
            output_files.append(str(out_path.name))

        JOBS[job_id].update(
            {
                "status": "done",
                "stats": stats,
                "output_files": output_files,
            }
        )
        db.update_job(
            job_id,
            status="done",
            requested=stats["requested"],
            placed=stats["placed"],
            sheet_count=stats["sheet_count"],
            is_all_placed=1 if stats["is_all_placed"] else 0,
            output_files=output_files,
            finished_at=datetime.now().isoformat(),
        )
    except Exception as e:
        JOBS[job_id].update(
            {
                "status": "error",
                "error": str(e),
            }
        )
        db.update_job(
            job_id,
            status="error",
            error=str(e),
            finished_at=datetime.now().isoformat(),
        )
    finally:
        for entry in file_entries:
            p = entry.get("path")
            c = entry.get("cleaned_path")
            if p:
                Path(p).unlink(missing_ok=True)
            if c and c != p:
                Path(c).unlink(missing_ok=True)
        job_upload_dir = UPLOAD_DIR / job_id
        if job_upload_dir.exists():
            shutil.rmtree(job_upload_dir, ignore_errors=True)


@app.post("/api/nest")
async def nest(
    request: Request,
    background_tasks: BackgroundTasks,
    sheetWidth: float = Form(...),
    sheetHeight: float = Form(...),
    space: float = Form(...),
    sheetCount: int = Form(1),
    addOutShape: bool = Form(False),
    project_id: Optional[int] = Form(None),
    files: List[UploadFile] = File(default=[]),
    counts: str = Form(...),
    rotations: str = Form(default="[]"),
):
    session = request.state.session
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        counts_list = json.loads(counts)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid counts JSON")

    try:
        rotations_list = json.loads(rotations)
    except Exception:
        rotations_list = [[] for _ in files]

    if not project_id and not files:
        raise HTTPException(status_code=400, detail="Files or project_id required")

    if not project_id and len(counts_list) != len(files):
        raise HTTPException(status_code=400, detail="Length of counts must match number of files")

    if not project_id and len(rotations_list) != len(files):
        rotations_list = [[] for _ in files]

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "status": "pending",
        "stats": None,
        "output_files": [],
        "error": None,
    }

    db_project_id = None
    if project_id:
        proj = db.get_project(session["session_id"], project_id)
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")
        db_project_id = project_id
    elif session:
        # no project_id, but we can associate with a dummy project later if needed
        pass

    db.create_job(db_project_id, job_id)

    job_upload_dir = UPLOAD_DIR / job_id
    job_upload_dir.mkdir(parents=True, exist_ok=True)

    file_entries = []

    if project_id:
        proj = db.get_project(session["session_id"], project_id)
        for f in proj["files"]:
            drawing = read_dxf(f["cleaned_content"])
            if drawing is None:
                raise HTTPException(status_code=400, detail=f"Could not parse saved DXF: {f['filename']}")
            parts = build_geometry(drawing, tolerance=0.1)
            temp_path = job_upload_dir / f["filename"]
            drawing.saveas(str(temp_path))
            file_entries.append(
                {
                    "path": str(temp_path),
                    "cleaned_path": str(temp_path),
                    "parts": parts,
                    "count": f["count"],
                    "rotations": json.loads(f["rotations"]) if f["rotations"] else [0.0, 90.0, 180.0, 270.0],
                }
            )
    else:
        for idx, upload in enumerate(files):
            file_path = job_upload_dir / upload.filename
            with open(file_path, "wb") as f:
                shutil.copyfileobj(upload.file, f)

            drawing = read_dxf(open(file_path, "rb"))
            if drawing is None:
                raise HTTPException(status_code=400, detail=f"Could not parse DXF: {upload.filename}")

            parts = build_geometry(drawing, tolerance=0.1)

            cleaned_path = job_upload_dir / f"cleaned_{upload.filename}"
            drawing.saveas(str(cleaned_path))

            file_entries.append(
                {
                    "path": str(file_path),
                    "cleaned_path": str(cleaned_path),
                    "parts": parts,
                    "count": counts_list[idx],
                    "rotations": rotations_list[idx] if rotations_list[idx] else [0.0, 90.0, 180.0, 270.0],
                }
            )

    background_tasks.add_task(
        process_job,
        job_id,
        sheetWidth,
        sheetHeight,
        space,
        sheetCount,
        addOutShape,
        file_entries,
        db_project_id,
    )

    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def status(job_id: str):
    if job_id not in JOBS:
        job = db.get_job_by_job_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {
            "status": job["status"],
            "stats": {
                "requested": job["requested"],
                "placed": job["placed"],
                "sheet_count": job["sheet_count"],
                "is_all_placed": bool(job["is_all_placed"]),
            } if job["requested"] is not None else None,
            "output_files": json.loads(job["output_files"]) if job["output_files"] else [],
            "error": job["error"],
        }
    job = JOBS[job_id]
    return {
        "status": job["status"],
        "stats": job.get("stats"),
        "output_files": job.get("output_files"),
        "error": job.get("error"),
    }


@app.get("/api/result/{job_id}/{filename}")
async def result(job_id: str, filename: str):
    if job_id not in JOBS:
        job = db.get_job_by_job_id(job_id)
        if not job or job["status"] != "done":
            raise HTTPException(status_code=400, detail="Job not completed yet")
    else:
        job = JOBS[job_id]
        if job["status"] != "done":
            raise HTTPException(status_code=400, detail="Job not completed yet")

    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File missing")
    return FileResponse(str(file_path), media_type="application/octet-stream", filename=filename)


@app.get("/api/result/{job_id}")
async def result_all(job_id: str):
    if job_id not in JOBS:
        job = db.get_job_by_job_id(job_id)
        if not job or job["status"] != "done":
            raise HTTPException(status_code=400, detail="Job not completed yet")
    else:
        job = JOBS[job_id]
        if job["status"] != "done":
            raise HTTPException(status_code=400, detail="Job not completed yet")

    if not job.get("output_files"):
        raise HTTPException(status_code=404, detail="No output files")
    if len(job["output_files"]) == 1:
        fname = job["output_files"][0]
        return FileResponse(str(OUTPUT_DIR / fname), media_type="application/octet-stream", filename=fname)
    raise HTTPException(status_code=400, detail="Multiple sheets available, download individually")
