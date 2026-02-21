import json

import libsql_client
from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_api_key
from app.database import get_client
from app.models import ExpenseCreate, ExpenseUpdate, ExpenseResponse

router = APIRouter()


def _row_to_expense(row) -> ExpenseResponse:
    # columns: id, title, amount, tag, category, location, description,
    #          payor_id, participants, trip_id, created_at, updated_at
    participants = json.loads(row[8]) if row[8] else None
    return ExpenseResponse(
        id=row[0],
        title=row[1],
        amount=row[2],
        tag=row[3],
        category=row[4],
        location=row[5],
        description=row[6],
        payor_id=row[7],
        participants=participants,
        trip_id=row[9],
        created_at=row[10],
        updated_at=row[11],
    )


async def _validate_payor(payor_id: int):
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement("SELECT id FROM users WHERE id = ?", [payor_id])
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Payor not found")


async def _validate_trip(trip_id: int):
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement("SELECT id FROM trips WHERE id = ?", [trip_id])
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Trip not found")


async def _validate_participants_in_trip(participants: list[int], trip_id: int | None):
    """Raises 400 if trip_id is absent, 404 if trip not found or any participant
    is not in the trip's participants list."""
    if trip_id is None:
        raise HTTPException(
            status_code=400, detail="trip_id required when participants are specified"
        )
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement("SELECT participants FROM trips WHERE id = ?", [trip_id])
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Trip not found")
    trip_participants = json.loads(rs.rows[0][0]) if rs.rows[0][0] else []
    invalid = [p for p in participants if p not in trip_participants]
    if invalid:
        raise HTTPException(
            status_code=404, detail=f"Participants not in trip: {invalid}"
        )


@router.post("/", status_code=201, dependencies=[Depends(require_api_key)])
async def create_expense(body: ExpenseCreate) -> ExpenseResponse:
    if body.payor_id is not None:
        await _validate_payor(body.payor_id)
    if body.participants:
        await _validate_participants_in_trip(body.participants, body.trip_id)
    elif body.trip_id is not None:
        await _validate_trip(body.trip_id)
    participants_json = json.dumps(body.participants) if body.participants else None
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "INSERT INTO expenses (title, amount, tag, category, location, description, "
            "payor_id, participants, trip_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING *",
            [body.title, body.amount, body.tag, body.category, body.location,
             body.description, body.payor_id, participants_json, body.trip_id],
        )
    )
    return _row_to_expense(rs.rows[0])


@router.get("/", dependencies=[Depends(require_api_key)])
async def list_expenses() -> list[ExpenseResponse]:
    client = get_client()
    rs = await client.execute("SELECT * FROM expenses ORDER BY created_at DESC")
    return [_row_to_expense(row) for row in rs.rows]


@router.get("/{expense_id}", dependencies=[Depends(require_api_key)])
async def get_expense(expense_id: int) -> ExpenseResponse:
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement("SELECT * FROM expenses WHERE id = ?", [expense_id])
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Expense not found")
    return _row_to_expense(rs.rows[0])


@router.patch("/{expense_id}", dependencies=[Depends(require_api_key)])
async def update_expense(expense_id: int, body: ExpenseUpdate) -> ExpenseResponse:
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "payor_id" in updates:
        await _validate_payor(updates["payor_id"])

    if "participants" in updates:
        trip_id = updates.get("trip_id")
        if trip_id is None:
            # Fetch the expense's current trip_id to validate against
            client = get_client()
            rs = await client.execute(
                libsql_client.Statement(
                    "SELECT trip_id FROM expenses WHERE id = ?", [expense_id]
                )
            )
            if rs.rows:
                trip_id = rs.rows[0][0]
        await _validate_participants_in_trip(updates["participants"], trip_id)
        updates["participants"] = json.dumps(updates["participants"])
    elif "trip_id" in updates:
        await _validate_trip(updates["trip_id"])

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    values.append(expense_id)

    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            f"UPDATE expenses SET {set_clause}, updated_at = datetime('now') "
            f"WHERE id = ? RETURNING *",
            values,
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Expense not found")
    return _row_to_expense(rs.rows[0])


@router.delete("/{expense_id}", dependencies=[Depends(require_api_key)])
async def delete_expense(expense_id: int):
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "DELETE FROM expenses WHERE id = ? RETURNING id", [expense_id]
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"message": "deleted"}
