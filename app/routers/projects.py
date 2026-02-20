import libsql_client
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user, require_org_access
from app.database import get_client
from app.models import (
    ProjectCreate, ProjectUpdate, ProjectResponse,
    EpicCreate, EpicUpdate, EpicResponse,
    TaskCreate, TaskUpdate, TaskResponse,
)

router = APIRouter()


# ── helpers ──────────────────────────────────────────────────────────────


async def _get_org_or_404(org_id: int):
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement("SELECT id FROM organizations WHERE id = ?", [org_id])
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Organization not found")


def _row_to_project(row) -> ProjectResponse:
    return ProjectResponse(
        id=row[0],
        title=row[1],
        description=row[2],
        status=row[3],
        created_at=row[4],
        updated_at=row[5],
        owner_id=row[6],
        organization_id=row[7],
    )


def _row_to_epic(row) -> EpicResponse:
    return EpicResponse(
        id=row[0],
        project_id=row[1],
        title=row[2],
        description=row[3],
        status=row[4],
        created_at=row[5],
        updated_at=row[6],
    )


def _row_to_task(row) -> TaskResponse:
    return TaskResponse(
        id=row[0],
        epic_id=row[1],
        title=row[2],
        description=row[3],
        deadline=row[4],
        status=row[5],
        label=row[6],
        created_at=row[7],
        updated_at=row[8],
    )


# ── Projects ─────────────────────────────────────────────────────────────


@router.post("/", status_code=201)
async def create_project(
    body: ProjectCreate,
    user: dict | None = Depends(get_current_user),
) -> ProjectResponse:
    await _get_org_or_404(body.organization_id)
    owner_id = user["id"] if user else None
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "INSERT INTO projects (title, description, status, owner_id, organization_id) "
            "VALUES (?, ?, ?, ?, ?) RETURNING *",
            [body.title, body.description, body.status, owner_id, body.organization_id],
        )
    )
    return _row_to_project(rs.rows[0])


@router.get("/")
async def list_projects(
    user: dict | None = Depends(get_current_user),
) -> list[ProjectResponse]:
    client = get_client()
    if user is None:
        # Settings key: see all projects
        rs = await client.execute("SELECT * FROM projects ORDER BY created_at DESC")
    else:
        # User: see only projects in their org
        rs = await client.execute(
            libsql_client.Statement(
                "SELECT * FROM projects WHERE organization_id = ? ORDER BY created_at DESC",
                [user["organization_id"]],
            )
        )
    return [_row_to_project(row) for row in rs.rows]


@router.get("/{project_id}")
async def get_project(
    project_id: int,
    user: dict | None = Depends(get_current_user),
) -> ProjectResponse:
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement("SELECT * FROM projects WHERE id = ?", [project_id])
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Project not found")
    await require_org_access(project_id, user)
    return _row_to_project(rs.rows[0])


@router.patch("/{project_id}")
async def update_project(
    project_id: int,
    body: ProjectUpdate,
    user: dict | None = Depends(get_current_user),
) -> ProjectResponse:
    await require_org_access(project_id, user)
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "organization_id" in updates:
        await _get_org_or_404(updates["organization_id"])

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    values.append(project_id)

    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            f"UPDATE projects SET {set_clause}, updated_at = datetime('now') "
            f"WHERE id = ? RETURNING *",
            values,
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Project not found")
    return _row_to_project(rs.rows[0])


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    user: dict | None = Depends(get_current_user),
):
    await require_org_access(project_id, user)
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "DELETE FROM projects WHERE id = ? RETURNING id", [project_id]
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": "deleted"}


# ── Epics ────────────────────────────────────────────────────────────────


async def _get_project_or_404(project_id: int):
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement("SELECT id FROM projects WHERE id = ?", [project_id])
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Project not found")


@router.post("/{project_id}/epics", status_code=201)
async def create_epic(
    project_id: int,
    body: EpicCreate,
    user: dict | None = Depends(get_current_user),
) -> EpicResponse:
    await require_org_access(project_id, user)
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "INSERT INTO epics (project_id, title, description, status) "
            "VALUES (?, ?, ?, ?) RETURNING *",
            [project_id, body.title, body.description, body.status],
        )
    )
    return _row_to_epic(rs.rows[0])


@router.get("/{project_id}/epics")
async def list_epics(
    project_id: int,
    user: dict | None = Depends(get_current_user),
) -> list[EpicResponse]:
    await require_org_access(project_id, user)
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT * FROM epics WHERE project_id = ? ORDER BY created_at DESC",
            [project_id],
        )
    )
    return [_row_to_epic(row) for row in rs.rows]


@router.get("/{project_id}/epics/{epic_id}")
async def get_epic(
    project_id: int,
    epic_id: int,
    user: dict | None = Depends(get_current_user),
) -> EpicResponse:
    await require_org_access(project_id, user)
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT * FROM epics WHERE id = ? AND project_id = ?",
            [epic_id, project_id],
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Epic not found")
    return _row_to_epic(rs.rows[0])


@router.patch("/{project_id}/epics/{epic_id}")
async def update_epic(
    project_id: int,
    epic_id: int,
    body: EpicUpdate,
    user: dict | None = Depends(get_current_user),
) -> EpicResponse:
    await require_org_access(project_id, user)
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    values.extend([epic_id, project_id])

    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            f"UPDATE epics SET {set_clause}, updated_at = datetime('now') "
            f"WHERE id = ? AND project_id = ? RETURNING *",
            values,
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Epic not found")
    return _row_to_epic(rs.rows[0])


@router.delete("/{project_id}/epics/{epic_id}")
async def delete_epic(
    project_id: int,
    epic_id: int,
    user: dict | None = Depends(get_current_user),
):
    await require_org_access(project_id, user)
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "DELETE FROM epics WHERE id = ? AND project_id = ? RETURNING id",
            [epic_id, project_id],
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Epic not found")
    return {"message": "deleted"}


# ── Tasks ────────────────────────────────────────────────────────────────


async def _get_epic_or_404(project_id: int, epic_id: int):
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT id FROM epics WHERE id = ? AND project_id = ?",
            [epic_id, project_id],
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Epic not found")


@router.post("/{project_id}/epics/{epic_id}/tasks", status_code=201)
async def create_task(
    project_id: int,
    epic_id: int,
    body: TaskCreate,
    user: dict | None = Depends(get_current_user),
) -> TaskResponse:
    await require_org_access(project_id, user)
    await _get_epic_or_404(project_id, epic_id)
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "INSERT INTO tasks (epic_id, title, description, deadline, status, label) "
            "VALUES (?, ?, ?, ?, ?, ?) RETURNING *",
            [epic_id, body.title, body.description, body.deadline, body.status, body.label],
        )
    )
    return _row_to_task(rs.rows[0])


@router.get("/{project_id}/epics/{epic_id}/tasks")
async def list_tasks(
    project_id: int,
    epic_id: int,
    user: dict | None = Depends(get_current_user),
) -> list[TaskResponse]:
    await require_org_access(project_id, user)
    await _get_epic_or_404(project_id, epic_id)
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT * FROM tasks WHERE epic_id = ? ORDER BY created_at DESC",
            [epic_id],
        )
    )
    return [_row_to_task(row) for row in rs.rows]


@router.get("/{project_id}/epics/{epic_id}/tasks/{task_id}")
async def get_task(
    project_id: int,
    epic_id: int,
    task_id: int,
    user: dict | None = Depends(get_current_user),
) -> TaskResponse:
    await require_org_access(project_id, user)
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT * FROM tasks WHERE id = ? AND epic_id = ?",
            [task_id, epic_id],
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Task not found")
    return _row_to_task(rs.rows[0])


@router.patch("/{project_id}/epics/{epic_id}/tasks/{task_id}")
async def update_task(
    project_id: int,
    epic_id: int,
    task_id: int,
    body: TaskUpdate,
    user: dict | None = Depends(get_current_user),
) -> TaskResponse:
    await require_org_access(project_id, user)
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    values.extend([task_id, epic_id])

    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            f"UPDATE tasks SET {set_clause}, updated_at = datetime('now') "
            f"WHERE id = ? AND epic_id = ? RETURNING *",
            values,
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Task not found")
    return _row_to_task(rs.rows[0])


@router.delete("/{project_id}/epics/{epic_id}/tasks/{task_id}")
async def delete_task(
    project_id: int,
    epic_id: int,
    task_id: int,
    user: dict | None = Depends(get_current_user),
):
    await require_org_access(project_id, user)
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "DELETE FROM tasks WHERE id = ? AND epic_id = ? RETURNING id",
            [task_id, epic_id],
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "deleted"}
