"""Tests for database module (app/database.py)."""

import os
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


class TestGetClient:
    def test_returns_client(self):
        import app.database as db
        # Reset cached client
        db._client = None
        with patch("app.database.libsql_client") as mock_lib:
            mock_lib.create_client.return_value = MagicMock()
            client = db.get_client()
            assert client is not None
            mock_lib.create_client.assert_called_once()

    def test_caches_client(self):
        import app.database as db
        db._client = None
        with patch("app.database.libsql_client") as mock_lib:
            mock_lib.create_client.return_value = MagicMock()
            client1 = db.get_client()
            client2 = db.get_client()
            assert client1 is client2
            # Should only be created once
            assert mock_lib.create_client.call_count == 1

    def test_converts_libsql_to_https(self):
        import app.database as db
        db._client = None
        original_url = os.environ.get("TURSO_DATABASE_URL")
        os.environ["TURSO_DATABASE_URL"] = "libsql://my-db.turso.io"
        try:
            with patch("app.database.libsql_client") as mock_lib:
                mock_lib.create_client.return_value = MagicMock()
                db.get_client()
                call_kwargs = mock_lib.create_client.call_args
                assert call_kwargs[1]["url"] == "https://my-db.turso.io"
        finally:
            if original_url:
                os.environ["TURSO_DATABASE_URL"] = original_url
            db._client = None

    def test_passes_auth_token(self):
        import app.database as db
        db._client = None
        original_token = os.environ.get("TURSO_AUTH_TOKEN")
        os.environ["TURSO_AUTH_TOKEN"] = "test-token-123"
        try:
            with patch("app.database.libsql_client") as mock_lib:
                mock_lib.create_client.return_value = MagicMock()
                db.get_client()
                call_kwargs = mock_lib.create_client.call_args
                assert call_kwargs[1]["auth_token"] == "test-token-123"
        finally:
            if original_token:
                os.environ["TURSO_AUTH_TOKEN"] = original_token
            db._client = None


class TestInitDb:
    @pytest.mark.asyncio
    async def test_creates_tables(self):
        import app.database as db
        mock_client = AsyncMock()
        # init_db also checks for api_key — return no rows so it generates one
        no_rows = MagicMock()
        no_rows.rows = []
        mock_client.execute.return_value = no_rows
        db._client = None
        with patch("app.database.get_client", return_value=mock_client):
            await db.init_db()
        mock_client.batch.assert_called_once()
        statements = mock_client.batch.call_args[0][0]
        assert len(statements) == 5
        # Verify all five tables
        all_sql = " ".join(statements)
        assert "todos" in all_sql
        assert "documents" in all_sql
        assert "embeddings" in all_sql
        assert "settings" in all_sql
        # Settings table should have created_at and expires_at columns
        settings_sql = [s for s in statements if "settings" in s][0]
        assert "created_at" in settings_sql
        assert "expires_at" in settings_sql

    @pytest.mark.asyncio
    async def test_generates_key_when_none_exists(self):
        import app.database as db
        mock_client = AsyncMock()
        # SELECT for api_key returns no rows
        no_rows = MagicMock()
        no_rows.rows = []
        mock_client.execute.return_value = no_rows
        db._client = None
        with patch("app.database.get_client", return_value=mock_client):
            await db.init_db()
        # 2 ALTER TABLE (migration) + SELECT check + INSERT OR REPLACE = 4
        assert mock_client.execute.call_count == 4
        insert_stmt = mock_client.execute.call_args_list[3][0][0]
        assert "INSERT OR REPLACE INTO settings" in insert_stmt.sql
        assert "expires_at" in insert_stmt.sql
        # Generated key should be a non-empty string
        assert len(insert_stmt.args[0]) > 0

    @pytest.mark.asyncio
    async def test_generates_key_when_expired(self):
        import app.database as db
        mock_client = AsyncMock()
        # SELECT returns a key with an expired timestamp
        expired = MagicMock()
        expired.rows = [("old-key", "2020-01-01 00:00:00")]
        # datetime('now') returns current time (after the expiry)
        now_result = MagicMock()
        now_result.rows = [("2025-01-01 00:00:00",)]
        # 2 ALTER TABLE + SELECT key + SELECT now + INSERT = 5 calls
        alter_ok = MagicMock()
        mock_client.execute.side_effect = [
            alter_ok, alter_ok, expired, now_result, MagicMock()
        ]
        db._client = None
        with patch("app.database.get_client", return_value=mock_client):
            await db.init_db()
        assert mock_client.execute.call_count == 5
        insert_stmt = mock_client.execute.call_args_list[4][0][0]
        assert "INSERT OR REPLACE INTO settings" in insert_stmt.sql

    @pytest.mark.asyncio
    async def test_skips_generation_when_key_valid(self):
        import app.database as db
        mock_client = AsyncMock()
        # SELECT returns a key with a future expiry
        valid = MagicMock()
        valid.rows = [("existing-key", "2099-01-01 00:00:00")]
        # datetime('now') returns current time (before expiry)
        now_result = MagicMock()
        now_result.rows = [("2025-01-01 00:00:00",)]
        # 2 ALTER TABLE + SELECT key + SELECT now = 4 calls
        alter_ok = MagicMock()
        mock_client.execute.side_effect = [
            alter_ok, alter_ok, valid, now_result
        ]
        db._client = None
        with patch("app.database.get_client", return_value=mock_client):
            await db.init_db()
        # No INSERT — just the 4 calls
        assert mock_client.execute.call_count == 4
