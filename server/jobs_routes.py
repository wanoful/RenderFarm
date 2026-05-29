import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from auth import get_current_user
import models

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "shared-storage"
JOB_DIR = Path(__file__).resolve().parent / "storage"


class SubmitSettings(BaseModel):
    name: str
    frame_start: int
    frame_end: int
    chunk_size: int = 1
    output_format: str = "PNG"


class ChunkUpdate(BaseModel):
    success: bool
    error: str = ""


@router.get("")
def list_jobs(user: str = Depends(get_current_user)):
    return models.get_jobs(user)


@router.post("")
async def submit_job(
    file: UploadFile = File(...),
    settings: str = Form(...),
    user: str = Depends(get_current_user),
):
    try:
        s = SubmitSettings.model_validate_json(settings)
    except Exception:
        raise HTTPException(400, "Invalid settings JSON")

    ext = Path(file.filename).suffix.lower()
    if ext not in (".blend", ".zip"):
        raise HTTPException(400, "File must be .blend or .zip")

    job = models.create_job(
        user=user,
        name=s.name,
        frame_start=s.frame_start,
        frame_end=s.frame_end,
        chunk_size=s.chunk_size,
        output_format=s.output_format,
        blend_filename=file.filename,
    )

    storage_dir = JOB_DIR / job["id"]
    storage_dir.mkdir(parents=True, exist_ok=True)
    dest = storage_dir / file.filename

    content = await file.read()
    dest.write_bytes(content)

    if ext == ".zip":
        try:
            with zipfile.ZipFile(dest) as zf:
                zf.extractall(storage_dir)
        except zipfile.BadZipFile:
            pass

    return job


@router.get("/{job_id}")
def get_job(job_id: str, user: str = Depends(get_current_user)):
    job = models.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/{job_id}/output")
def download_output(job_id: str, user: str = Depends(get_current_user)):
    job = models.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    out_dir = STORAGE_DIR / job_id
    if not out_dir.exists() or not list(out_dir.iterdir()):
        raise HTTPException(404, "No output yet")

    def generate():
        import subprocess
        with subprocess.Popen(
            ["zip", "-rq", "-", "."],
            cwd=str(out_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ) as proc:
            while True:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                yield chunk
            proc.wait()

    return StreamingResponse(
        generate(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={job_id}_output.zip"},
    )


@router.delete("/{job_id}")
def delete_job(job_id: str, user: str = Depends(get_current_user)):
    job = models.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] in ("pending", "running"):
        models.cancel_job(job_id)
        return {"status": "cancelled"}
    if job["status"] in ("completed", "failed", "cancelled"):
        models.delete_job(job_id)
        return {"status": "deleted"}
    raise HTTPException(400, f"Cannot handle status: {job['status']}")


@router.post("/claim")
def claim(
    user: str = Depends(get_current_user),
    worker: str = Query(..., description="Worker name"),
):
    conn = models._connect()
    chunk = conn.execute(
        """SELECT c.id, c.job_id, c.frame_start, c.frame_end, c.status,
                  j.output_format, j.blend_filename
           FROM job_chunks c JOIN jobs j ON c.job_id = j.id
           WHERE c.status = 'pending' AND j.status IN ('pending', 'running')
           ORDER BY c.id LIMIT 1"""
    ).fetchone()
    if chunk is None:
        conn.close()
        raise HTTPException(204, "No pending chunks")

    conn.execute(
        "UPDATE job_chunks SET status = 'running', worker = ? WHERE id = ?",
        (worker, chunk["id"]),
    )
    conn.execute(
        "UPDATE jobs SET status = 'running', started_at = COALESCE(started_at, ?)"
        " WHERE id = ? AND status = 'pending'",
        (datetime.now(timezone.utc).isoformat(), chunk["job_id"]),
    )
    conn.commit()
    conn.close()
    return dict(chunk)


@router.put("/{job_id}/chunks/{chunk_id}")
def update_chunk(
    job_id: str,
    chunk_id: int,
    body: ChunkUpdate,
    user: str = Depends(get_current_user),
    worker: str = Query(..., description="Worker name"),
):
    models.complete_chunk(job_id, chunk_id, worker, body.success, body.error)
    return {"status": "ok"}


@router.get("/{job_id}/files/{filename}")
def download_job_file(job_id: str, filename: str, user: str = Depends(get_current_user), worker: str = Query(..., description="Worker name")):
    file_path = JOB_DIR / job_id / filename
    if not file_path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(file_path, filename=filename)


@router.post("/{job_id}/frames")
async def upload_frames(
    job_id: str,
    file: UploadFile = File(...),
    user: str = Depends(get_current_user),
    worker: str = Query(..., description="Worker name"),
):
    job = models.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    out_dir = STORAGE_DIR / job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    dest = out_dir / file.filename
    dest.write_bytes(content)

    return {"filename": file.filename, "size": len(content)}
