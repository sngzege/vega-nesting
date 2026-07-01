import pytest
import app.database as db


@pytest.fixture(autouse=True)
def _clean_db():
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs")
    cursor.execute("DELETE FROM project_files")
    cursor.execute("DELETE FROM projects")
    cursor.execute("DELETE FROM sessions")
    cursor.execute("DELETE FROM users")
    conn.commit()
    conn.close()
    yield


def test_user_creation():
    uid = db.get_or_create_user("alice")
    assert uid > 0
    uid2 = db.get_or_create_user("alice")
    assert uid == uid2


def test_session():
    uid = db.get_or_create_user("bob")
    sid = db.create_session(uid)
    session = db.get_session(sid)
    assert session is not None
    assert session["username"] == "bob"
    assert db.get_session("nonexistent") is None


def test_project_crud():
    uid = db.get_or_create_user("carol")
    sid = db.create_session(uid)
    files = [
        {
            "filename": "part.dxf",
            "original_content": b"MOCK",
            "cleaned_content": b"MOCK",
            "count": 1,
            "rotations": [0, 90],
        }
    ]
    pid = db.create_project(sid, "Test", 100.0, 200.0, 1.0, 1, False, files)
    assert pid > 0

    projects = db.get_projects(sid)
    assert len(projects) == 1
    assert projects[0]["name"] == "Test"

    project = db.get_project(sid, pid)
    assert project["project"]["sheet_width"] == 100.0
    assert len(project["files"]) == 1

    assert db.delete_project(sid, pid)
    assert len(db.get_projects(sid)) == 0


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
