import json

import libsql_client
from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_api_key
from app.database import get_client
from app.models import ExpenseCreate, ExpenseUpdate, ExpenseResponse

router = APIRouter()


def _row_to_expense(row) -> ExpenseResponse:
    shared_with = json.loads(row[8]) if row[8] else None
    return ExpenseResponse(
        id=row[0],
        title=row[1],
        amount=row[2],
        tag=row[3],
        category=row[4],
        location=row[5],
        description=row[6],
        paid_by=row[7],
        shared_with=shared_with,
        created_at=row[9],
        updated_at=row[10],
    )


@router.post("/", status_code=201, dependencies=[Depends(require_api_key)])
async def create_expense(body: ExpenseCreate) -> ExpenseResponse:
    client = get_client()
    shared_with_json = json.dumps(body.shared_with) if body.shared_with else None
    rs = await client.execute(
        libsql_client.Statement(
            "INSERT INTO expenses (title, amount, tag, category, location, description, paid_by, shared_with) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING *",
            [body.title, body.amount, body.tag, body.category, body.location,
             body.description, body.paid_by, shared_with_json],
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

    if "shared_with" in updates:
        updates["shared_with"] = json.dumps(updates["shared_with"])

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
