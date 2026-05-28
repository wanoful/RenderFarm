import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yaml
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "users.yaml"
_users_cache: dict[str, str] = {}
_cache_time: Optional[datetime] = None


def _load_users() -> dict[str, str]:
    global _users_cache, _cache_time
    if _cache_time and datetime.now() - _cache_time < timedelta(minutes=5):
        return _users_cache
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    _users_cache = config.get("users", {})
    _cache_time = datetime.now()
    return _users_cache


def verify_password(username: str, password: str) -> bool:
    users = _load_users()
    return username in users and secrets.compare_digest(users[username], password)


def get_current_user(
    credentials: HTTPBasicCredentials = Depends(security),
) -> str:
    if not verify_password(credentials.username, credentials.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
