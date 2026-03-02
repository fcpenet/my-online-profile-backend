import libsql_client
from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_api_key
from app.database import get_client
from app.models import TagCreate, TagResponse

router = APIRouter()


def _row_to_tag(row) -> TagResponse:
    # columns: id, name, created_at
    return TagResponse(id=row[0], name=row[1], created_at=row[2])


@router.post("/", status_code=201, dependencies=[Depends(require_api_key)])
async def create_tag(body: TagCreate) -> TagResponse:
    client = get_client()
    try:
        rs = await client.execute(
            libsql_client.Statement(
                "INSERT INTO tags (name) VALUES (?) RETURNING *",
                [body.name],
            )
        )
    except Exception:
        raise HTTPException(status_code=409, detail="Tag name already exists")
    return _row_to_tag(rs.rows[0])


@router.get("/", dependencies=[Depends(require_api_key)])
async def list_tags() -> list[TagResponse]:
    client = get_client()
    rs = await client.execute("SELECT * FROM tags ORDER BY name ASC")
    return [_row_to_tag(row) for row in rs.rows]


@router.get("/{tag_id}", dependencies=[Depends(require_api_key)])
async def get_tag(tag_id: int) -> TagResponse:
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement("SELECT * FROM tags WHERE id = ?", [tag_id])
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Tag not found")
    return _row_to_tag(rs.rows[0])


@router.delete("/{tag_id}", dependencies=[Depends(require_api_key)])
async def delete_tag(tag_id: int):
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement("DELETE FROM tags WHERE id = ? RETURNING id", [tag_id])
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"message": "deleted"}
