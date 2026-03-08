import libsql_client
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.database import get_client

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user(api_key: str = Security(api_key_header)) -> dict | None:
    """Authenticate via user token. Raises 401 if no key, 403 if invalid.

    Returns dict with {"id": int, "organization_id": int | None, "role": str}.
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT u.id, u.organization_id, u.role "
            "FROM tokens t LEFT JOIN users u ON t.user_id = u.id "
            "WHERE t.token = ? "
            "AND (t.expires_at IS NULL OR t.expires_at > datetime('now')) "
            "AND (t.max_uses = 0 OR t.uses < t.max_uses)",
            [api_key],
        )
    )
    if rs.rows:
        row = rs.rows[0]
        if row[0] is None:
            return None  # Valid token with no associated user
        return {"id": row[0], "organization_id": row[1], "role": row[2]}
    raise HTTPException(status_code=403, detail="Invalid API key")


async def require_api_key(api_key: str = Security(api_key_header)):
    """Validates key but discards user info."""
    await get_current_user(api_key)


async def require_admin(api_key: str = Security(api_key_header)):
    """Accepts a valid token linked to a user with role='admin'."""
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT t.max_uses, t.uses, t.expires_at, u.role "
            "FROM tokens t LEFT JOIN users u ON t.user_id = u.id "
            "WHERE t.token = ?",
            [api_key],
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=403, detail="Invalid token")

    max_uses, uses, expires_at, role = rs.rows[0]

    if expires_at is not None:
        now_rs = await client.execute("SELECT datetime('now')")
        if now_rs.rows[0][0] >= expires_at:
            raise HTTPException(status_code=403, detail="Token has expired")

    if max_uses != 0 and uses >= max_uses:
        raise HTTPException(status_code=403, detail="Token has no uses remaining")

    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")


async def require_org_access(project_id: int, user: dict | None):
    """Raises 404 if project doesn't exist.
    Raises 403 if user's org doesn't match the project's org."""
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT organization_id FROM projects WHERE id = ?", [project_id]
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Project not found")
    if user is None:
        return
    project_org_id = rs.rows[0][0]
    if project_org_id is not None and project_org_id != user.get("organization_id"):
        raise HTTPException(status_code=403, detail="Access denied")
