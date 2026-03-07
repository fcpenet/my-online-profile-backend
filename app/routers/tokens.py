import secrets

import libsql_client
from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_admin
from app.database import get_client
from app.models import TokenCreate, TokenResponse, TokenValidateResponse

router = APIRouter()


def _row_to_token(row) -> TokenResponse:
    # columns: id, token, max_uses, uses, expires_at, created_at
    return TokenResponse(
        id=row[0],
        token=row[1],
        max_uses=row[2],
        uses=row[3],
        expires_at=row[4],
        created_at=row[5],
    )


@router.post("/", status_code=201, dependencies=[Depends(require_admin)])
async def create_token(body: TokenCreate) -> TokenResponse:
    token_value = secrets.token_urlsafe(32)
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "INSERT INTO tokens (token, max_uses, expires_at) VALUES (?, ?, ?) RETURNING *",
            [token_value, body.max_uses, body.expires_at],
        )
    )
    return _row_to_token(rs.rows[0])


@router.get("/", dependencies=[Depends(require_admin)])
async def list_tokens() -> list[TokenResponse]:
    client = get_client()
    rs = await client.execute("SELECT * FROM tokens ORDER BY created_at DESC")
    return [_row_to_token(row) for row in rs.rows]


@router.get("/validate/{token}")
async def validate_token(token: str) -> TokenValidateResponse:
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT id, token, max_uses, uses, expires_at, created_at, "
            "(expires_at IS NULL OR expires_at > datetime('now')) as not_expired "
            "FROM tokens WHERE token = ?",
            [token],
        )
    )
    if not rs.rows:
        return TokenValidateResponse(valid=False, uses_remaining=None, expires_at=None)

    row = rs.rows[0]
    max_uses = row[2]
    uses = row[3]
    expires_at = row[4]
    not_expired = bool(row[6])

    exhausted = max_uses != 0 and uses >= max_uses
    valid = not_expired and not exhausted
    uses_remaining = None if max_uses == 0 else max(0, max_uses - uses)

    return TokenValidateResponse(valid=valid, uses_remaining=uses_remaining, expires_at=expires_at)


@router.post("/use/{token}")
async def use_token(token: str) -> TokenResponse:
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement("SELECT * FROM tokens WHERE token = ?", [token])
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Token not found")

    row = rs.rows[0]
    max_uses = row[2]
    uses = row[3]
    expires_at = row[4]

    if expires_at is not None:
        now_rs = await client.execute("SELECT datetime('now')")
        now = now_rs.rows[0][0]
        if now >= expires_at:
            raise HTTPException(status_code=410, detail="Token has expired")

    if max_uses != 0 and uses >= max_uses:
        raise HTTPException(status_code=410, detail="Token has no uses remaining")

    rs = await client.execute(
        libsql_client.Statement(
            "UPDATE tokens SET uses = uses + 1 WHERE token = ? RETURNING *",
            [token],
        )
    )
    return _row_to_token(rs.rows[0])


@router.get("/{token_id}", dependencies=[Depends(require_admin)])
async def get_token(token_id: int) -> TokenResponse:
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement("SELECT * FROM tokens WHERE id = ?", [token_id])
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Token not found")
    return _row_to_token(rs.rows[0])


@router.delete("/{token_id}", dependencies=[Depends(require_admin)])
async def delete_token(token_id: int):
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "DELETE FROM tokens WHERE id = ? RETURNING id", [token_id]
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"message": "deleted"}
