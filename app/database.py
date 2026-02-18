import asyncio
import logging
import os
import secrets

import libsql_client

logger = logging.getLogger(__name__)


_client = None


def get_client() -> libsql_client.Client:
    global _client
    if _client is None:
        url = os.environ["TURSO_DATABASE_URL"]
        # libsql-client needs https://, not libsql://
        url = url.replace("libsql://", "https://")
        _client = libsql_client.create_client(
            url=url,
            auth_token=os.environ.get("TURSO_AUTH_TOKEN"),
        )
    return _client


async def close_client():
    global _client
    if _client is not None:
        await _client.close()
        # Allow aiohttp's underlying SSL transport to fully shut down
        await asyncio.sleep(0.25)
        _client = None


async def init_db():
    client = get_client()
    await client.batch(
        [
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT 'Untitled',
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                embedding TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                amount REAL NOT NULL,
                tag TEXT,
                category TEXT,
                location TEXT,
                description TEXT,
                paid_by TEXT NOT NULL,
                shared_with TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS epics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                epic_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                deadline TEXT,
                status TEXT NOT NULL DEFAULT 'todo',
                label TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (epic_id) REFERENCES epics(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at TEXT
            )
            """,
        ]
    )
    # Migrate: add columns if the settings table predates the schema change
    for col, defn in [
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("expires_at", "TEXT"),
    ]:
        try:
            await client.execute(f"ALTER TABLE settings ADD COLUMN {col} {defn}")
        except Exception:
            pass  # Column already exists

    # Ensure a valid (non-expired) API key exists — generate one if missing or expired
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT value, expires_at FROM settings WHERE key = ?", ["api_key"]
        )
    )
    needs_new_key = True
    if rs.rows:
        expires_at = rs.rows[0][1]
        # Valid if expires_at is in the future (compared as ISO 8601 strings)
        if expires_at:
            now = await client.execute("SELECT datetime('now')")
            needs_new_key = now.rows[0][0] >= expires_at
    if needs_new_key:
        new_key = secrets.token_urlsafe(32)
        await client.execute(
            libsql_client.Statement(
                """INSERT OR REPLACE INTO settings (key, value, created_at, expires_at)
                   VALUES ('api_key', ?, datetime('now'), datetime('now', '+24 hours'))""",
                [new_key],
            )
        )
        logger.info("New API key created in the database")
