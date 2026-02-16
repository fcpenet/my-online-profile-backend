import libsql_client
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_api_key, clear_api_key_cache
from app.database import get_client

router = APIRouter()


class RotateKeyRequest(BaseModel):
    new_key: str


@router.get("/verify-key", dependencies=[Depends(require_api_key)])
async def verify_key():
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT expires_at FROM settings WHERE key = ?", ["api_key"]
        )
    )
    expires_at = rs.rows[0][0] if rs.rows else None
    return {"valid": True, "expires_at": expires_at}


@router.post("/rotate-key", dependencies=[Depends(require_api_key)])
async def rotate_key(body: RotateKeyRequest):
    if len(body.new_key) < 8:
        raise HTTPException(status_code=400, detail="Key must be at least 8 characters")
    client = get_client()
    await client.execute(
        libsql_client.Statement(
            """UPDATE settings
               SET value = ?, created_at = datetime('now'), expires_at = datetime('now', '+24 hours')
               WHERE key = 'api_key'""",
            [body.new_key],
        )
    )
    clear_api_key_cache()
    return {"message": "API key rotated"}
