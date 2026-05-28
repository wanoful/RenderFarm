import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from fastapi import FastAPI
from auth import verify_password
from models import init_db
from jobs_routes import router as jobs_router

app = FastAPI(title="RenderFarm", version="1.0.0")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/auth/login")
def login(username: str, password: str):
    if verify_password(username, password):
        return {"status": "ok", "user": username}
    return {"status": "error", "detail": "Invalid credentials"}, 401


app.include_router(jobs_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="10.80.73.62", port=8000, reload=False)
