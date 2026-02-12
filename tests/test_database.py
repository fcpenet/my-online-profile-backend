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
        db._client = None
        with patch("app.database.get_client", return_value=mock_client):
            await db.init_db()
        mock_client.batch.assert_called_once()
        statements = mock_client.batch.call_args[0][0]
        assert len(statements) == 4
        # Verify all four tables
        all_sql = " ".join(statements)
        assert "todos" in all_sql
        assert "documents" in all_sql
        assert "embeddings" in all_sql
        assert "settings" in all_sql

    @pytest.mark.asyncio
    async def test_seeds_api_key_from_env(self):
        import app.database as db
        mock_client = AsyncMock()
        db._client = None
        os.environ["API_KEY"] = "seed-test-key"
        with patch("app.database.get_client", return_value=mock_client):
            await db.init_db()
        # Should have called execute for the seed INSERT OR IGNORE
        mock_client.execute.assert_called_once()
        stmt = mock_client.execute.call_args[0][0]
        assert "INSERT OR IGNORE" in stmt.sql
        assert stmt.args == ["seed-test-key"]

    @pytest.mark.asyncio
    async def test_skips_seed_when_no_env_key(self):
        import app.database as db
        mock_client = AsyncMock()
        db._client = None
        original = os.environ.pop("API_KEY", None)
        try:
            with patch("app.database.get_client", return_value=mock_client):
                await db.init_db()
            # Should NOT call execute for seeding
            mock_client.execute.assert_not_called()
        finally:
            if original:
                os.environ["API_KEY"] = original
