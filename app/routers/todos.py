import libsql_client
from fastapi import APIRouter, HTTPException

from app.database import get_client
from app.models import TodoCreate, TodoUpdate, TodoResponse

router = APIRouter()


def _row_to_todo(row) -> TodoResponse:
    return TodoResponse(
        id=row[0],
        title=row[1],
        description=row[2],
        completed=bool(row[3]),
        created_at=row[4],
        updated_at=row[5],
    )


@router.post("/", status_code=201)
async def create_todo(body: TodoCreate) -> TodoResponse:
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "INSERT INTO todos (title, description) VALUES (?, ?) RETURNING *",
            [body.title, body.description],
        )
    )
    return _row_to_todo(rs.rows[0])


@router.get("/")
async def list_todos() -> list[TodoResponse]:
    client = get_client()
    rs = await client.execute("SELECT * FROM todos ORDER BY created_at DESC")
    return [_row_to_todo(row) for row in rs.rows]


@router.get("/{todo_id}")
async def get_todo(todo_id: int) -> TodoResponse:
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement("SELECT * FROM todos WHERE id = ?", [todo_id])
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Todo not found")
    return _row_to_todo(rs.rows[0])


@router.patch("/{todo_id}")
async def update_todo(todo_id: int, body: TodoUpdate) -> TodoResponse:
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Map Python bool to SQLite integer for the completed field
    if "completed" in updates:
        updates["completed"] = int(updates["completed"])

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    values.append(todo_id)

    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            f"UPDATE todos SET {set_clause}, updated_at = datetime('now') "
            f"WHERE id = ? RETURNING *",
            values,
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Todo not found")
    return _row_to_todo(rs.rows[0])


@router.delete("/{todo_id}")
async def delete_todo(todo_id: int):
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "DELETE FROM todos WHERE id = ? RETURNING id", [todo_id]
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Todo not found")
    return {"message": "deleted"}
