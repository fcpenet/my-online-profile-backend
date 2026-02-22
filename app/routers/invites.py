import secrets

import libsql_client
from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_settings_key
from app.database import get_client
from app.models import InviteCreate, InviteResponse

router = APIRouter()


def _row_to_invite(row) -> InviteResponse:
    # columns: id, code, max_uses, uses, created_at
    return InviteResponse(
        id=row[0],
        code=row[1],
        max_uses=row[2],
        uses=row[3],
        created_at=row[4],
    )


@router.post("/", status_code=201, dependencies=[Depends(require_settings_key)])
async def create_invite(body: InviteCreate) -> InviteResponse:
    code = body.code or secrets.token_urlsafe(8)
    client = get_client()
    try:
        rs = await client.execute(
            libsql_client.Statement(
                "INSERT INTO invites (code, max_uses) VALUES (?, ?) RETURNING *",
                [code, body.max_uses],
            )
        )
    except Exception:
        raise HTTPException(status_code=409, detail="Invite code already exists")
    return _row_to_invite(rs.rows[0])


@router.get("/", dependencies=[Depends(require_settings_key)])
async def list_invites() -> list[InviteResponse]:
    client = get_client()
    rs = await client.execute("SELECT * FROM invites ORDER BY created_at DESC")
    return [_row_to_invite(row) for row in rs.rows]


@router.delete("/{invite_id}", dependencies=[Depends(require_settings_key)])
async def delete_invite(invite_id: int):
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "DELETE FROM invites WHERE id = ? RETURNING id", [invite_id]
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Invite not found")
    return {"message": "deleted"}
