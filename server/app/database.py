import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

DATABASE_PATH = Path(__file__).resolve().parent / "vega_nesting.db"


def get_connection():
    conn = sqlite3.connect(str(DATABASE_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            name TEXT NOT NULL,
            sheet_width REAL,
            sheet_height REAL,
            space REAL,
            sheet_count INTEGER,
            status TEXT DEFAULT 'draft',
            sheet_material TEXT DEFAULT 'ST37',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS project_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_content BLOB,
            cleaned_content BLOB,
            count INTEGER NOT NULL,
            rotations TEXT,
            sort_order INTEGER,
            material TEXT,
            thickness TEXT,
            FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            job_id TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'pending',
            requested INTEGER,
            placed INTEGER,
            sheet_count INTEGER,
            is_all_placed INTEGER,
            output_files TEXT,
            output_names TEXT,
            error TEXT,
            started_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects (id)
        );
        """
    )

    cursor.execute("PRAGMA table_info(projects)")
    project_cols = {row["name"] for row in cursor.fetchall()}
    if "sheet_material" not in project_cols:
        cursor.execute("ALTER TABLE projects ADD COLUMN sheet_material TEXT DEFAULT 'ST37'")

    cursor.execute("PRAGMA table_info(project_files)")
    file_cols = {row["name"] for row in cursor.fetchall()}
    if "material" not in file_cols:
        cursor.execute("ALTER TABLE project_files ADD COLUMN material TEXT")
    if "thickness" not in file_cols:
        cursor.execute("ALTER TABLE project_files ADD COLUMN thickness TEXT")

    cursor.execute("PRAGMA table_info(jobs)")
    job_cols = {row["name"] for row in cursor.fetchall()}
    if "output_names" not in job_cols:
        cursor.execute("ALTER TABLE jobs ADD COLUMN output_names TEXT")

    conn.commit()
    conn.close()


# Users & sessions


def get_or_create_user(username: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (username) VALUES (?)", (username,)
    )
    conn.commit()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    return user["id"]


def create_session(user_id: int) -> str:
    session_id = str(uuid.uuid4())
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (id, user_id) VALUES (?, ?)", (session_id, user_id)
    )
    conn.commit()
    conn.close()
    return session_id


def get_session(session_id: str):
    if not session_id:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT s.id as session_id, s.user_id, u.username
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.id = ?
        """,
        (session_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def delete_session(session_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


# Projects


def create_project(
    session_id: str,
    name: str,
    sheet_width: float,
    sheet_height: float,
    space: float,
    sheet_count: int,
    files: list,
    sheet_material: str = "ST37",
) -> int:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO projects (session_id, name, sheet_width, sheet_height, space, sheet_count, sheet_material)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            name,
            sheet_width,
            sheet_height,
            space,
            sheet_count,
            sheet_material,
        ),
    )
    project_id = cursor.lastrowid

    for idx, f in enumerate(files):
        cursor.execute(
            """
            INSERT INTO project_files
                (project_id, filename, original_content, cleaned_content, count, rotations, sort_order, material, thickness)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                f["filename"],
                f["original_content"],
                f["cleaned_content"],
                f["count"],
                json.dumps(
                    f.get("rotations", [0.0, 90.0, 180.0, 270.0])
                ),
                idx,
                f.get("material"),
                f.get("thickness"),
            ),
        )

    conn.commit()
    conn.close()
    return project_id


def update_project(
    project_id: int,
    session_id: str,
    name: str,
    sheet_width: float,
    sheet_height: float,
    space: float,
    sheet_count: int,
    files: list,
    sheet_material: str = "ST37",
) -> bool:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE projects
        SET name = ?, sheet_width = ?, sheet_height = ?, space = ?, sheet_count = ?, sheet_material = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND session_id = ?
        """,
        (
            name,
            sheet_width,
            sheet_height,
            space,
            sheet_count,
            sheet_material,
            project_id,
            session_id,
        ),
    )

    if cursor.rowcount == 0:
        conn.close()
        return False

    cursor.execute("DELETE FROM project_files WHERE project_id = ?", (project_id,))
    for idx, f in enumerate(files):
        cursor.execute(
            """
            INSERT INTO project_files
                (project_id, filename, original_content, cleaned_content, count, rotations, sort_order, material, thickness)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                f["filename"],
                f["original_content"],
                f["cleaned_content"],
                f["count"],
                json.dumps(
                    f.get("rotations", [0.0, 90.0, 180.0, 270.0])
                ),
                idx,
                f.get("material"),
                f.get("thickness"),
            ),
        )

    conn.commit()
    conn.close()
    return True


def get_projects(session_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, name, sheet_width, sheet_height, space, sheet_count, status, sheet_material, created_at, updated_at
        FROM projects
        WHERE session_id = ?
        ORDER BY updated_at DESC
        """,
        (session_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_project(session_id: str, project_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, name, sheet_width, sheet_height, space, sheet_count, status, sheet_material, created_at, updated_at
        FROM projects
        WHERE id = ? AND session_id = ?
        """,
        (project_id, session_id),
    )
    project = cursor.fetchone()
    if not project:
        conn.close()
        return None

    cursor.execute(
        """
        SELECT id, filename, count, rotations, sort_order, material, thickness
        FROM project_files
        WHERE project_id = ?
        ORDER BY sort_order
        """,
        (project_id,),
    )
    project_files = cursor.fetchall()
    conn.close()

    return {
        "project": dict(project),
        "files": [dict(f) for f in project_files],
    }


def delete_project(session_id: str, project_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM projects WHERE id = ? AND session_id = ?",
        (project_id, session_id),
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# Jobs


def create_job(project_id: Optional[int], job_id: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO jobs (project_id, job_id) VALUES (?, ?)",
        (project_id, job_id),
    )
    job_db_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return job_db_id


def get_job_by_job_id(job_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, project_id, job_id, status, requested, placed, sheet_count, is_all_placed, output_files, error, created_at, finished_at
        FROM jobs WHERE job_id = ?
        """,
        (job_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def update_job(job_id: str, **kwargs):
    conn = get_connection()
    cursor = conn.cursor()

    set_parts = []
    values = []
    for key, value in kwargs.items():
        if key == "output_files":
            set_parts.append("output_files = ?")
            values.append(json.dumps(value))
        elif key in ("finished_at", "started_at", "created_at"):
            set_parts.append(f"{key} = ?")
            values.append(value)
        else:
            set_parts.append(f"{key} = ?")
            values.append(value)
    values.append(job_id)

    query = f"UPDATE jobs SET {', '.join(set_parts)} WHERE job_id = ?"
    cursor.execute(query, values)
    conn.commit()
    conn.close()
