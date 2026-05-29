import sys
import zipfile
import tempfile
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse, Response
from auth import verify_password
from models import init_db
from jobs_routes import router as jobs_router

app = FastAPI(title="RenderFarm", version="1.0.0")

SHARED_STORAGE = Path(__file__).resolve().parent.parent / "shared-storage"
SHARED_STORAGE.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/auth/login")
def login(username: str, password: str):
    if verify_password(username, password):
        return {"status": "ok", "user": username}
    return {"status": "error", "detail": "Invalid credentials"}, 401


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/output/{path:path}")
def browse_output(path: str = ""):
    full = (SHARED_STORAGE / path).resolve()
    if not str(full).startswith(str(SHARED_STORAGE.resolve())):
        return PlainTextResponse("Not found", 404)

    if path.endswith("/_download.zip"):
        parent = full.parent
        if not parent.is_dir():
            return PlainTextResponse("Not found", 404)
        zd, tmp_path = tempfile.mkstemp(suffix=".zip")
        os.close(zd)
        try:
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in sorted(parent.iterdir()):
                    if f.is_file():
                        zf.write(f, f.name)
        except Exception:
            os.unlink(tmp_path)
            return PlainTextResponse("Failed", 500)
        return _cleanup_file_response(tmp_path, parent.name + ".zip")

    if not full.exists():
        return PlainTextResponse("Not found", 404)

    if not full.exists():
        return PlainTextResponse("Not found", 404)

    if path.endswith("/_download.zip"):
        parent = full.parent
        if not parent.is_dir():
            return PlainTextResponse("Not found", 404)
        zd, tmp_path = tempfile.mkstemp(suffix=".zip")
        os.close(zd)
        try:
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in sorted(parent.iterdir()):
                    if f.is_file() and f.name != "_download.zip":
                        zf.write(f, f.name)
        except Exception:
            os.unlink(tmp_path)
            return PlainTextResponse("Failed", 500)
        return _cleanup_file_response(tmp_path, parent.name + ".zip")

    if full.is_file():
        return FileResponse(full)

    items = sorted(full.iterdir(), key=lambda x: (not x.is_dir(), x.name))
    name = full.name
    html = "<html><head><title>%s</title>" % name
    html += "<style>body{font:14px monospace;margin:20px}a{text-decoration:none}"
    html += "a.f{color:#333}a.d{color:#06c}</style></head><body>"
    html += f"<h2>/output/{path}</h2>"
    html += f'<p><a href="{path.rstrip("/")}/_download.zip">Download All as ZIP</a></p>'
    html += "<hr>"
    if path:
        parent = "/output/" + "/".join(path.split("/")[:-1])
        html += f'<p><a href="{parent}">..</a></p>'
    for item in items:
        item_name = item.name
        href = f"/output/{path}/{item_name}" if path else f"/output/{item_name}"
        cls = "d" if item.is_dir() else "f"
        size = f" {item.stat().st_size:,}B" if item.is_file() else ""
        html += f'<p><a class="{cls}" href="{href}">{item_name}</a>{size}</p>'
    html += "</body></html>"
    return HTMLResponse(html)


def _cleanup_file_response(path: str, filename: str):
    class CleanupResponse(FileResponse):
        def __init__(self, p, fn):
            self._tmp = p
            super().__init__(p, filename=fn, media_type="application/zip")

        async def __call__(self, scope, receive, send):
            try:
                await super().__call__(scope, receive, send)
            finally:
                try:
                    os.unlink(self._tmp)
                except OSError:
                    pass

    return CleanupResponse(path, filename)


app.include_router(jobs_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="10.80.73.62", port=8000, reload=False)
