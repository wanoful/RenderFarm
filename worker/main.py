import atexit
import os
import shutil
import signal
import time
import sys
from pathlib import Path

import requests

from blender_runner import run_render, find_blender

SERVER_URL = os.environ.get("RENDERFARM_SERVER", "http://10.80.73.62:8000")
WORKER_NAME = os.environ.get("RENDERFARM_WORKER", "worker1")
SERVER_AUTH = (
    os.environ.get("RENDERFARM_USER", "worker"),
    os.environ.get("RENDERFARM_PASS", "worker"),
)

POLL_INTERVAL = 5

TMP_DIR = Path(os.environ.get("RENDERFARM_TMP", "/tmp/renderfarm-worker"))
_running = True


def _clean_tmp():
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR, ignore_errors=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)


def _shutdown(*_):
    global _running
    print("[worker] Shutting down, cleaning up...")
    _running = False
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR, ignore_errors=True)
    sys.exit(0)


def download_job_files(job_id: str, blend_filename: str, dest_dir: Path) -> list[Path]:
    if not blend_filename:
        return []

    try:
        r = requests.get(
            f"{SERVER_URL}/api/jobs/{job_id}/files/{blend_filename}?worker={WORKER_NAME}",
            auth=SERVER_AUTH,
            timeout=60,
        )
        if not r.ok:
            return []

        dest = dest_dir / blend_filename
        dest.write_bytes(r.content)
        return [dest]
    except requests.RequestException:
        return []


def upload_frames(job_id: str, frames: list[str]) -> int:
    uploaded = 0
    for path in frames:
        p = Path(path)
        with open(p, "rb") as f:
            r = requests.post(
                f"{SERVER_URL}/api/jobs/{job_id}/frames?worker={WORKER_NAME}",
                files={"file": (p.name, f)},
                auth=SERVER_AUTH,
            )
            if r.ok:
                uploaded += 1
    return uploaded


def process_chunk() -> bool:
    try:
        r = requests.post(
            f"{SERVER_URL}/api/jobs/claim",
            params={"worker": WORKER_NAME},
            auth=SERVER_AUTH,
            timeout=30,
        )
    except requests.RequestException as e:
        print(f"[worker] Cannot reach server: {e}")
        time.sleep(POLL_INTERVAL)
        return False

    if r.status_code == 204:
        time.sleep(POLL_INTERVAL)
        return False

    if not r.ok:
        print(f"[worker] Claim error: {r.status_code} {r.text}")
        time.sleep(POLL_INTERVAL)
        return False

    chunk = r.json()
    job_id = chunk["job_id"]
    chunk_id = chunk["id"]
    frame_start = chunk["frame_start"]
    frame_end = chunk["frame_end"]
    fmt = chunk.get("output_format", "PNG")
    blend_filename = chunk.get("blend_filename", "")

    print(f"[worker] Claimed job={job_id} chunk={chunk_id} "
          f"frames={frame_start}-{frame_end}")

    chunk_dir = TMP_DIR / f"{job_id}-{chunk_id}"
    if chunk_dir.exists():
        shutil.rmtree(chunk_dir)
    chunk_dir.mkdir(parents=True, exist_ok=True)

    try:
        files = download_job_files(job_id, blend_filename, chunk_dir)
        blend_files = [f for f in files if f.suffix.lower() == ".blend"]

        if not blend_files:
            _update_chunk(job_id, chunk_id, False, "No .blend file found")
            return True

        blend_file = str(blend_files[0])

        success, message, frames = run_render(
            blend_file=blend_file,
            output_dir=str(chunk_dir),
            frame_start=frame_start,
            frame_end=frame_end,
            output_format=fmt,
        )

        if not success:
            _update_chunk(job_id, chunk_id, False, message)
            return True

        uploaded = upload_frames(job_id, frames)
        print(f"[worker] Rendered {len(frames)} frames, uploaded {uploaded}")

        _update_chunk(job_id, chunk_id, True, "")
    finally:
        if chunk_dir.exists():
            shutil.rmtree(chunk_dir)

    return True


def _update_chunk(job_id: str, chunk_id: int, success: bool, error: str = ""):
    try:
        requests.put(
            f"{SERVER_URL}/api/jobs/{job_id}/chunks/{chunk_id}?worker={WORKER_NAME}",
            json={"success": success, "error": error},
            auth=SERVER_AUTH,
            timeout=30,
        )
    except requests.RequestException as e:
        print(f"[worker] Update error: {e}")


def main():
    blender = find_blender()
    if not blender:
        print("[worker] Blender not found!")
        sys.exit(1)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    _clean_tmp()
    atexit.register(lambda: shutil.rmtree(TMP_DIR, ignore_errors=True))

    print(f"[worker] Blender: {blender}")
    print(f"[worker] Server: {SERVER_URL}")
    print(f"[worker] Worker: {WORKER_NAME}")
    print(f"[worker] Temp dir: {TMP_DIR}")

    while _running:
        try:
            process_chunk()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[worker] Error: {e}")
            time.sleep(POLL_INTERVAL)

    _shutdown()


if __name__ == "__main__":
    main()
