import libsql_client
from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_api_key
from app.database import get_client
from app.models import OrganizationCreate, OrganizationUpdate, OrganizationResponse

router = APIRouter()


def _row_to_org(row) -> OrganizationResponse:
    return OrganizationResponse(
        id=row[0],
        name=row[1],
        created_at=row[2],
        updated_at=row[3],
    )


@router.post("/", status_code=201, dependencies=[Depends(require_api_key)])
async def create_organization(body: OrganizationCreate) -> OrganizationResponse:
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "INSERT INTO organizations (name) VALUES (?) RETURNING *",
            [body.name],
        )
    )
    return _row_to_org(rs.rows[0])


@router.get("/", dependencies=[Depends(require_api_key)])
async def list_organizations() -> list[OrganizationResponse]:
    client = get_client()
    rs = await client.execute("SELECT * FROM organizations ORDER BY created_at DESC")
    return [_row_to_org(row) for row in rs.rows]


@router.get("/{org_id}", dependencies=[Depends(require_api_key)])
async def get_organization(org_id: int) -> OrganizationResponse:
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement("SELECT * FROM organizations WHERE id = ?", [org_id])
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _row_to_org(rs.rows[0])


@router.patch("/{org_id}", dependencies=[Depends(require_api_key)])
async def update_organization(org_id: int, body: OrganizationUpdate) -> OrganizationResponse:
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    values.append(org_id)

    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            f"UPDATE organizations SET {set_clause}, updated_at = datetime('now') "
            f"WHERE id = ? RETURNING *",
            values,
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _row_to_org(rs.rows[0])


@router.delete("/{org_id}", dependencies=[Depends(require_api_key)])
async def delete_organization(org_id: int):
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "DELETE FROM organizations WHERE id = ? RETURNING id", [org_id]
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"message": "deleted"}
