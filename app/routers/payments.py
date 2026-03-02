import json

import libsql_client
from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_api_key
from app.database import get_client
from app.models import PaymentCreate, PaymentUpdate, PaymentResponse

router = APIRouter()


def _row_to_payment(row) -> PaymentResponse:
    # columns: id, date, expenses, tags, created_at, updated_at
    return PaymentResponse(
        id=row[0],
        date=row[1],
        expense_ids=json.loads(row[2]) if row[2] else None,
        tag_ids=json.loads(row[3]) if row[3] else None,
        created_at=row[4],
        updated_at=row[5],
    )


async def _validate_expense_ids(expense_ids: list[int]):
    client = get_client()
    placeholders = ", ".join("?" * len(expense_ids))
    rs = await client.execute(
        libsql_client.Statement(
            f"SELECT id FROM expenses WHERE id IN ({placeholders})",
            expense_ids,
        )
    )
    found = {row[0] for row in rs.rows}
    invalid = [e for e in expense_ids if e not in found]
    if invalid:
        raise HTTPException(status_code=404, detail=f"Expenses not found: {invalid}")


async def _validate_tag_ids(tag_ids: list[int]):
    client = get_client()
    placeholders = ", ".join("?" * len(tag_ids))
    rs = await client.execute(
        libsql_client.Statement(
            f"SELECT id FROM tags WHERE id IN ({placeholders})",
            tag_ids,
        )
    )
    found = {row[0] for row in rs.rows}
    invalid = [t for t in tag_ids if t not in found]
    if invalid:
        raise HTTPException(status_code=404, detail=f"Tags not found: {invalid}")


@router.post("/", status_code=201, dependencies=[Depends(require_api_key)])
async def create_payment(body: PaymentCreate) -> PaymentResponse:
    if body.expense_ids:
        await _validate_expense_ids(body.expense_ids)
    if body.tag_ids:
        await _validate_tag_ids(body.tag_ids)

    expenses_json = json.dumps(body.expense_ids) if body.expense_ids else None
    tags_json = json.dumps(body.tag_ids) if body.tag_ids else None
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "INSERT INTO payments (date, expenses, tags) VALUES (?, ?, ?) RETURNING *",
            [body.date, expenses_json, tags_json],
        )
    )
    return _row_to_payment(rs.rows[0])


@router.get("/", dependencies=[Depends(require_api_key)])
async def list_payments() -> list[PaymentResponse]:
    client = get_client()
    rs = await client.execute("SELECT * FROM payments ORDER BY date DESC")
    return [_row_to_payment(row) for row in rs.rows]


@router.get("/{payment_id}", dependencies=[Depends(require_api_key)])
async def get_payment(payment_id: int) -> PaymentResponse:
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement("SELECT * FROM payments WHERE id = ?", [payment_id])
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Payment not found")
    return _row_to_payment(rs.rows[0])


@router.patch("/{payment_id}", dependencies=[Depends(require_api_key)])
async def update_payment(payment_id: int, body: PaymentUpdate) -> PaymentResponse:
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "expense_ids" in updates:
        await _validate_expense_ids(updates["expense_ids"])
        updates["expenses"] = json.dumps(updates.pop("expense_ids"))
    if "tag_ids" in updates:
        await _validate_tag_ids(updates["tag_ids"])
        updates["tags"] = json.dumps(updates.pop("tag_ids"))

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    values.append(payment_id)

    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            f"UPDATE payments SET {set_clause}, updated_at = datetime('now') "
            f"WHERE id = ? RETURNING *",
            values,
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Payment not found")
    return _row_to_payment(rs.rows[0])


@router.delete("/{payment_id}", dependencies=[Depends(require_api_key)])
async def delete_payment(payment_id: int):
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "DELETE FROM payments WHERE id = ? RETURNING id", [payment_id]
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {"message": "deleted"}
