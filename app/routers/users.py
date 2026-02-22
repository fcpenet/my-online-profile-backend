import secrets

import bcrypt
import libsql_client
from fastapi import APIRouter, HTTPException

from app.database import get_client
from app.models import UserRegister, UserLogin, UserResponse, LoginResponse

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
    client = get_client()

    # Validate invite code
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT id, uses, max_uses FROM invites WHERE code = ?", [body.invite_code]
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    invite_id, uses, max_uses = rs.rows[0]
    if uses >= max_uses:
        raise HTTPException(status_code=403, detail="Invite code exhausted")

    if body.organization_id is not None:
        await _get_org_or_404(body.organization_id)

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
            "RETURNING id, email, organization_id, created_at",
            [body.email, password_hash, body.organization_id],
        )
    )
    row = rs.rows[0]

    # Increment invite uses
    await client.execute(
        libsql_client.Statement(
            "UPDATE invites SET uses = uses + 1 WHERE id = ?", [invite_id]
        )
    )

    return UserResponse(id=row[0], email=row[1], organization_id=row[2], created_at=row[3])


@router.post("/login")
async def login(body: UserLogin) -> LoginResponse:
    client = get_client()

    # Look up user by email
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT id, password_hash, api_key, api_key_expires_at FROM users WHERE email = ?",
            [body.email],
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_id, password_hash, api_key, expires_at = rs.rows[0]

    if not _verify_password(body.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Check if existing key is still valid
    if api_key and expires_at:
        now_rs = await client.execute("SELECT datetime('now')")
        now = now_rs.rows[0][0]
        if now < expires_at:
            return LoginResponse(api_key=api_key, expires_at=expires_at)

    # Generate new key
    new_key = secrets.token_urlsafe(32)
    rs = await client.execute(
        libsql_client.Statement(
            "UPDATE users SET api_key = ?, api_key_expires_at = datetime('now', '+24 hours'), "
            "updated_at = datetime('now') WHERE id = ? RETURNING api_key_expires_at",
            [new_key, user_id],
        )
    )
    return LoginResponse(api_key=new_key, expires_at=rs.rows[0][0])
