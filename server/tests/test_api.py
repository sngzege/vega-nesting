import io
import time
import ezdxf
from unittest.mock import patch
from fastapi.testclient import TestClient
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import app.main as main_module
import app.database as db_module

TEST_DB_PATH = Path(__file__).parent.parent / "app" / "test_runtime.db"


@pytest.fixture(autouse=True)
def _clean_db():
    conn = db_module.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs")
    cursor.execute("DELETE FROM project_files")
    cursor.execute("DELETE FROM projects")
    cursor.execute("DELETE FROM sessions")
    cursor.execute("DELETE FROM users")
    conn.commit()
    conn.close()
    yield


@pytest.fixture(autouse=True)
def _temp_dirs(monkeypatch, tmp_path):
    monkeypatch.setattr(main_module, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(main_module, "OUTPUT_DIR", tmp_path / "output")
    for d in [tmp_path / "uploads", tmp_path / "output"]:
        d.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def client():
    return TestClient(main_module.app)


def _make_simple_dxf():
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0))
    msp.add_line((10, 0), (10, 10))
    msp.add_line((10, 10), (0, 10))
    msp.add_line((0, 10), (0, 0))
    buf = io.StringIO()
    doc.write(buf)
    text = buf.getvalue()
    return text.encode("utf-8")


def _login(client):
    client.post("/api/login", data={"username": "testuser"})


def _wait_for_job(client, job_id, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/status/{job_id}")
        data = resp.json()
        if data["status"] in ("done", "error"):
            return data
        time.sleep(0.2)
    raise AssertionError("Job did not finish in time")


def test_login(client):
    resp = client.post("/api/login", data={"username": "testuser"})
    assert resp.status_code == 200
    assert "session_id" in resp.cookies


def test_protected(client):
    resp = client.get("/api/projects")
    assert resp.status_code == 401


def _run_nest(client):
    buf = _make_simple_dxf()
    mock_output = {
        "solution": {
            "layouts": [
                {
                    "placed_items": [
                        {
                            "item_id": 0,
                            "transformation": {
                                "rotation": 0.0,
                                "translation": [0.0, 0.0],
                            },
                        }
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
                "sheetCount": "1",
                "addOutShape": "false",
                "counts": "[1]",
                "rotations": "[]",
            },
            files=[
                ("files", ("test.dxf", buf, "application/octet-stream")),
            ],
        )
    assert resp.status_code == 200
    return resp.json()["job_id"]


def test_nest_endpoint(client):
    _login(client)
    job_id = _run_nest(client)
    status_data = _wait_for_job(client, job_id)
    assert status_data["status"] == "done"


def test_preview_endpoint(client):
    _login(client)
    job_id = _run_nest(client)
    status_data = _wait_for_job(client, job_id)
    assert status_data["status"] == "done"

    resp = client.get(f"/api/preview/{job_id}/1")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/svg+xml"
    assert b"<svg" in resp.content

    resp = client.get(f"/api/preview/{job_id}/999")
    assert resp.status_code == 404

    resp = client.get("/api/preview/nonexistent/1")
    assert resp.status_code == 404


def test_result_with_custom_name(client):
    _login(client)
    job_id = _run_nest(client)
    status_data = _wait_for_job(client, job_id)
    assert status_data["status"] == "done"

    resp = client.get(f"/api/result/{job_id}?name=ozel-cikti")
    assert resp.status_code == 200
    cd = resp.headers.get("content-disposition", "")
    assert "ozel-cikti.dxf" in cd

    fname = status_data["output_files"][0]
    resp = client.get(f"/api/result/{job_id}/{fname}?name=parca-1")
    assert resp.status_code == 200
    cd = resp.headers.get("content-disposition", "")
    assert "parca-1.dxf" in cd
