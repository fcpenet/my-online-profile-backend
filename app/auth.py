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


async def get_current_user(api_key: str = Security(api_key_header)) -> dict | None:
    """Authenticate and return user info, or None for settings key (superuser).

    Returns dict with {"id": int, "organization_id": int | None} for user keys,
    or None for the settings key (which bypasses org checks).
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    # Check settings key (superuser — bypasses org checks)
    stored_key = await get_api_key()
    if stored_key and api_key == stored_key:
        return None
    # Check user API keys
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT id, organization_id FROM users WHERE api_key = ? AND api_key_expires_at > datetime('now')",
            [api_key],
        )
    )
    if rs.rows:
        return {"id": rs.rows[0][0], "organization_id": rs.rows[0][1]}
    raise HTTPException(status_code=403, detail="Invalid API key")


async def require_api_key(api_key: str = Security(api_key_header)):
    """Backwards-compatible auth dependency. Validates key but discards user info."""
    await get_current_user(api_key)


async def require_org_access(project_id: int, user: dict | None):
    """Raises 404 if project doesn't exist.
    Raises 403 if user's org doesn't match the project's org.
    Settings key (user=None) bypasses org checks but still verifies existence."""
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT organization_id FROM projects WHERE id = ?", [project_id]
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Project not found")
    if user is None:
        return  # Settings key = full access
    project_org_id = rs.rows[0][0]
    if project_org_id is not None and project_org_id != user.get("organization_id"):
        raise HTTPException(status_code=403, detail="Access denied")
