import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "renderfarm.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            user TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            frame_start INTEGER NOT NULL,
            frame_end INTEGER NOT NULL,
            chunk_size INTEGER NOT NULL DEFAULT 1,
            output_format TEXT NOT NULL DEFAULT 'PNG',
            blend_filename TEXT NOT NULL,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            error_message TEXT,
            total_frames INTEGER NOT NULL DEFAULT 0,
            rendered_frames INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            frame_start INTEGER NOT NULL,
            frame_end INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            worker TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()


def create_job(
    user: str,
    name: str,
    frame_start: int,
    frame_end: int,
    chunk_size: int,
    output_format: str,
    blend_filename: str,
) -> dict:
    job_id = uuid.uuid4().hex[:12]
    total_frames = abs(frame_end - frame_start) + 1
    now = datetime.now(timezone.utc).isoformat()

    conn = _connect()
    conn.execute(
        """INSERT INTO jobs
           (id, user, name, status, frame_start, frame_end, chunk_size,
            output_format, blend_filename, created_at, total_frames)
           VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?)""",
        (
            job_id, user, name, frame_start, frame_end, chunk_size,
            output_format, blend_filename, now, total_frames,
        ),
    )

    for chunk_start in range(frame_start, frame_end + 1, chunk_size):
        chunk_end = min(chunk_start + chunk_size - 1, frame_end)
        conn.execute(
            "INSERT INTO job_chunks (job_id, frame_start, frame_end) VALUES (?, ?, ?)",
            (job_id, chunk_start, chunk_end),
        )

    conn.commit()
    conn.close()

    out_dir = Path(__file__).parent.parent / "shared-storage" / job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    return {"id": job_id, "name": name, "status": "pending"}


def get_jobs(user: str) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM jobs WHERE user = ? ORDER BY created_at DESC", (user,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_job(job_id: str) -> Optional[dict]:
    conn = _connect()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        conn.close()
        return None
    job = dict(row)
    chunks = conn.execute(
        "SELECT * FROM job_chunks WHERE job_id = ? ORDER BY frame_start",
        (job_id,),
    ).fetchall()
    job["chunks"] = [dict(c) for c in chunks]
    conn.close()
    return job


def claim_chunk(job_id: str, worker: str) -> Optional[dict]:
    conn = _connect()
    chunk = conn.execute(
        """UPDATE job_chunks SET status = 'running', worker = ?
           WHERE job_id = ? AND status = 'pending'
           AND id = (SELECT MIN(id) FROM job_chunks WHERE job_id = ? AND status = 'pending')
           RETURNING *""",
        (worker, job_id, job_id),
    ).fetchone()

    if chunk is None:
        conn.close()
        return None

    conn.execute(
        "UPDATE jobs SET status = 'running', started_at = COALESCE(started_at, ?)"
        " WHERE id = ? AND status = 'pending'",
        (datetime.now(timezone.utc).isoformat(), job_id),
    )
    conn.commit()
    conn.close()
    return dict(chunk)


def complete_chunk(
    job_id: str, chunk_id: int, worker: str, success: bool, error: str = ""
) -> None:
    conn = _connect()
    status = "completed" if success else "failed"
    conn.execute(
        "UPDATE job_chunks SET status = ? WHERE id = ? AND job_id = ?",
        (status, chunk_id, job_id),
    )
    if success:
        chunk = conn.execute(
            "SELECT * FROM job_chunks WHERE id = ?", (chunk_id,)
        ).fetchone()
        chunk_frames = abs(chunk["frame_end"] - chunk["frame_start"]) + 1
        conn.execute(
            "UPDATE jobs SET rendered_frames = rendered_frames + ? WHERE id = ?",
            (chunk_frames, job_id),
        )

    remaining = conn.execute(
        "SELECT COUNT(*) FROM job_chunks WHERE job_id = ? AND status != 'completed'",
        (job_id,),
    ).fetchone()[0]

    if remaining == 0:
        conn.execute(
            "UPDATE jobs SET status = 'completed', finished_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), job_id),
        )

    conn.commit()
    conn.close()


def cancel_job(job_id: str) -> bool:
    conn = _connect()
    cur = conn.execute(
        "UPDATE jobs SET status = 'cancelled' WHERE id = ? AND status IN ('pending', 'running')",
        (job_id,),
    )
    ok = cur.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def delete_job(job_id: str) -> bool:
    conn = _connect()
    cur = conn.execute(
        "DELETE FROM jobs WHERE id = ? AND status IN ('completed', 'failed', 'cancelled')",
        (job_id,),
    )
    ok = cur.rowcount > 0
    conn.commit()
    conn.close()

    if ok:
        base = Path(__file__).parent
        for d in [
            base / "storage" / job_id,
            base.parent / "shared-storage" / job_id,
        ]:
            if d.exists():
                shutil.rmtree(d)

    return ok
