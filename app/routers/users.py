import secrets

import bcrypt
import libsql_client
from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_admin
from app.database import get_client
from app.models import UserRegister, UserLogin, UserResponse, LoginResponse, UserRoleUpdate

router = APIRouter()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


async def _get_org_or_404(org_id: int):
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement("SELECT id FROM organizations WHERE id = ?", [org_id])
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Organization not found")


@router.post("/register", status_code=201)
async def register(body: UserRegister) -> UserResponse:
    if body.organization_id is not None:
        await _get_org_or_404(body.organization_id)

    client = get_client()

    # Check if email already exists
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT id FROM users WHERE email = ?", [body.email]
        )
    )
    if rs.rows:
        raise HTTPException(status_code=409, detail="Email already registered")

    password_hash = _hash_password(body.password)
    rs = await client.execute(
        libsql_client.Statement(
            "INSERT INTO users (email, password_hash, organization_id) VALUES (?, ?, ?) "
            "RETURNING id, email, organization_id, role, created_at",
            [body.email, password_hash, body.organization_id],
        )
    )
    row = rs.rows[0]

    return UserResponse(id=row[0], email=row[1], organization_id=row[2], role=row[3], created_at=row[4])


@router.post("/login")
async def login(body: UserLogin) -> LoginResponse:
    client = get_client()

    # Look up user by email
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT id, password_hash FROM users WHERE email = ?",
            [body.email],
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_id, password_hash = rs.rows[0]

    if not _verify_password(body.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Return an existing valid token if one exists
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT token, expires_at FROM tokens "
            "WHERE user_id = ? "
            "AND (expires_at IS NULL OR expires_at > datetime('now')) "
            "AND (max_uses = 0 OR uses < max_uses) "
            "ORDER BY created_at DESC LIMIT 1",
            [user_id],
        )
    )
    if rs.rows:
        return LoginResponse(api_key=rs.rows[0][0], expires_at=rs.rows[0][1])

    # Create a new token with unlimited uses and 1-day expiry
    new_key = secrets.token_urlsafe(32)
    rs = await client.execute(
        libsql_client.Statement(
            "INSERT INTO tokens (token, max_uses, expires_at, user_id) "
            "VALUES (?, 0, datetime('now', '+1 day'), ?) "
            "RETURNING token, expires_at",
            [new_key, user_id],
        )
    )
    row = rs.rows[0]
    return LoginResponse(api_key=row[0], expires_at=row[1])


@router.patch("/{user_id}/role", dependencies=[Depends(require_admin)])
async def update_user_role(user_id: int, body: UserRoleUpdate) -> UserResponse:
    client = get_client()
    rs = await client.execute(
        libsql_client.Statement(
            "UPDATE users SET role = ?, updated_at = datetime('now') "
            "WHERE id = ? RETURNING id, email, organization_id, role, created_at",
            [body.role, user_id],
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="User not found")
    row = rs.rows[0]
    return UserResponse(id=row[0], email=row[1], organization_id=row[2], role=row[3], created_at=row[4])
