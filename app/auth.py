import time

import libsql_client
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.database import get_client

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

_cached_key: str | None = None
_cache_time: float = 0
_CACHE_TTL = 60  # seconds


async def get_api_key() -> str | None:
    """Fetch the API key from the DB if not expired, with a 60-second in-memory cache."""
    global _cached_key, _cache_time
    if _cached_key and (time.time() - _cache_time) < _CACHE_TTL:
        return _cached_key
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT value FROM settings WHERE key = ? AND expires_at > datetime('now')",
            ["api_key"],
        )
    )
    if rs.rows:
        _cached_key = rs.rows[0][0]
        _cache_time = time.time()
    else:
        _cached_key = None
        _cache_time = 0
    return _cached_key


def clear_api_key_cache():
    """Clear the cached key so the next request fetches from DB."""
    global _cached_key, _cache_time
    _cached_key = None
    _cache_time = 0


async def require_api_key(api_key: str = Security(api_key_header)):
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    # Check settings key (existing system)
    stored_key = await get_api_key()
    if stored_key and api_key == stored_key:
        return
    # Check user API keys
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT id FROM users WHERE api_key = ? AND api_key_expires_at > datetime('now')",
            [api_key],
        )
    )
    if rs.rows:
        return
    raise HTTPException(status_code=403, detail="Invalid API key")
