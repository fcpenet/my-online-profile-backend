import json

import libsql_client
from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_api_key
from app.database import get_client
from app.models import TripCreate, TripUpdate, TripResponse

router = APIRouter()


def _row_to_trip(row) -> TripResponse:
    # columns: id, title, description, start_date, end_date,
    #          participants, created_at, updated_at
    participants = json.loads(row[5]) if row[5] else None
    return TripResponse(
        id=row[0],
        title=row[1],
        description=row[2],
        start_date=row[3],
        end_date=row[4],
        participants=participants,
        created_at=row[6],
        updated_at=row[7],
    )


async def _validate_participants(user_ids: list[int]):
    """Raises 404 if any user_id in the list does not exist."""
    client = get_client()
    placeholders = ", ".join("?" for _ in user_ids)
    rs = await client.execute(
        libsql_client.Statement(
            f"SELECT id FROM users WHERE id IN ({placeholders})", user_ids
        )
    )
    found_ids = {row[0] for row in rs.rows}
    missing = [uid for uid in user_ids if uid not in found_ids]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Users not found: {missing}",
        )


@router.post("/", status_code=201, dependencies=[Depends(require_api_key)])
async def create_trip(body: TripCreate) -> TripResponse:
    if body.participants:
        await _validate_participants(body.participants)
    participants_json = json.dumps(body.participants) if body.participants else None
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "INSERT INTO trips (title, description, start_date, end_date, participants) "
            "VALUES (?, ?, ?, ?, ?) RETURNING *",
            [body.title, body.description, body.start_date, body.end_date, participants_json],
        )
    )
    return _row_to_trip(rs.rows[0])


@router.get("/", dependencies=[Depends(require_api_key)])
async def list_trips() -> list[TripResponse]:
    client = get_client()
    rs = await client.execute("SELECT * FROM trips ORDER BY created_at DESC")
    return [_row_to_trip(row) for row in rs.rows]


@router.get("/{trip_id}", dependencies=[Depends(require_api_key)])
async def get_trip(trip_id: int) -> TripResponse:
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement("SELECT * FROM trips WHERE id = ?", [trip_id])
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Trip not found")
    return _row_to_trip(rs.rows[0])


@router.patch("/{trip_id}", dependencies=[Depends(require_api_key)])
async def update_trip(trip_id: int, body: TripUpdate) -> TripResponse:
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "participants" in updates:
        await _validate_participants(updates["participants"])
        updates["participants"] = json.dumps(updates["participants"])

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    values.append(trip_id)

    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            f"UPDATE trips SET {set_clause}, updated_at = datetime('now') "
            f"WHERE id = ? RETURNING *",
            values,
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Trip not found")
    return _row_to_trip(rs.rows[0])


@router.delete("/{trip_id}", dependencies=[Depends(require_api_key)])
async def delete_trip(trip_id: int):
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement("DELETE FROM trips WHERE id = ? RETURNING id", [trip_id])
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Trip not found")
    return {"message": "deleted"}
