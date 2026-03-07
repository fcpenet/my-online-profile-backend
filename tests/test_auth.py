from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from tests.conftest import AUTH_HEADERS, mock_result


# --- Unit tests for require_api_key ---

class TestRequireApiKey:
    @pytest.mark.asyncio
    async def test_missing_key_raises_401(self):
        from app.auth import require_api_key
        with pytest.raises(HTTPException) as exc_info:
            await require_api_key(api_key=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_key_raises_401(self):
        from app.auth import require_api_key
        with pytest.raises(HTTPException) as exc_info:
            await require_api_key(api_key="")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_key_raises_403(self):
        from app.auth import require_api_key
        mock_client = AsyncMock()
        mock_client.execute.return_value = mock_result(rows=[])
        with patch("app.auth.get_client", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                await require_api_key(api_key="wrong-key")
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_token_raises_403(self):
        from app.auth import require_api_key
        mock_client = AsyncMock()
        mock_client.execute.return_value = mock_result(rows=[])
        with patch("app.auth.get_client", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                await require_api_key(api_key="any-key")
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_valid_token_passes(self):
        from app.auth import require_api_key
        mock_client = AsyncMock()
        mock_client.execute.return_value = mock_result(rows=[(1, None, "user")])
        with patch("app.auth.get_client", return_value=mock_client):
            result = await require_api_key(api_key="user-token")
        assert result is None


# --- Unit tests for require_admin ---

class TestRequireAdmin:
    @pytest.mark.asyncio
    async def test_missing_key_raises_401(self):
        from app.auth import require_admin
        with pytest.raises(HTTPException) as exc_info:
            await require_admin(api_key=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_admin_token_passes(self):
        from app.auth import require_admin
        mock_client = AsyncMock()
        # JOIN returns: max_uses=10, uses=1, expires_at=None, role="admin"
        mock_client.execute.return_value = mock_result(rows=[(10, 1, None, "admin")])
        with patch("app.auth.get_client", return_value=mock_client):
            result = await require_admin(api_key="some-token-value")
        assert result is None

    @pytest.mark.asyncio
    async def test_non_admin_token_raises_403(self):
        from app.auth import require_admin
        mock_client = AsyncMock()
        mock_client.execute.return_value = mock_result(rows=[(10, 1, None, "user")])
        with patch("app.auth.get_client", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                await require_admin(api_key="some-token-value")
        assert exc_info.value.status_code == 403
        assert "Admin role required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_token_no_user_raises_403(self):
        from app.auth import require_admin
        mock_client = AsyncMock()
        mock_client.execute.return_value = mock_result(rows=[(10, 1, None, None)])
        with patch("app.auth.get_client", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                await require_admin(api_key="some-token-value")
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_token_raises_403(self):
        from app.auth import require_admin
        mock_client = AsyncMock()
        mock_client.execute.return_value = mock_result(rows=[])
        with patch("app.auth.get_client", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                await require_admin(api_key="bad-token")
        assert exc_info.value.status_code == 403
        assert "Invalid token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_expired_token_raises_403(self):
        from app.auth import require_admin
        mock_client = AsyncMock()
        now_result = MagicMock()
        now_result.rows = [("2025-01-01 12:00:00",)]
        mock_client.execute.side_effect = [
            mock_result(rows=[(10, 1, "2020-01-01 00:00:00", "admin")]),
            now_result,
        ]
        with patch("app.auth.get_client", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                await require_admin(api_key="some-token-value")
        assert exc_info.value.status_code == 403
        assert "expired" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_exhausted_token_raises_403(self):
        from app.auth import require_admin
        mock_client = AsyncMock()
        mock_client.execute.return_value = mock_result(rows=[(5, 5, None, "admin")])
        with patch("app.auth.get_client", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                await require_admin(api_key="some-token-value")
        assert exc_info.value.status_code == 403
        assert "no uses remaining" in exc_info.value.detail


# --- Public endpoints: should work without any API key ---

class TestPublicEndpoints:
    def test_health_no_key(self, client):
        c, _ = client
        assert c.get("/api/health").status_code == 200

    def test_list_todos_no_key(self, client):
        c, _ = client
        assert c.get("/api/todos/").status_code == 200

    def test_get_todo_no_key(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(
            rows=[(1, "Test", "desc", 0, "2024-01-01", "2024-01-01")]
        )
        assert c.get("/api/todos/1").status_code == 200

    def test_list_documents_no_key(self, client):
        c, _ = client
        assert c.get("/api/rag/documents").status_code == 200

    def test_query_document_no_key(self, client):
        c, mock_db = client
        mock_db.execute.side_effect = [
            mock_result(rows=[(1,)]),
            mock_result(rows=[("chunk text", '[0.1, 0.2, 0.3]')]),
        ]
        with patch("app.routers.rag.get_embeddings", new_callable=AsyncMock) as mock_emb, \
             patch("app.routers.rag.generate_answer", new_callable=AsyncMock) as mock_gen:
            mock_emb.return_value = [[0.1, 0.2, 0.3]]
            mock_gen.return_value = "Test answer"
            resp = c.post("/api/rag/query", json={"question": "What is this?"})
        assert resp.status_code != 401
        assert resp.status_code != 403


# --- Protected endpoints: should return 401 without key ---

class TestProtectedNoKey:
    def test_create_todo(self, client):
        c, _ = client
        assert c.post("/api/todos/", json={"title": "test"}).status_code == 401

    def test_update_todo(self, client):
        c, _ = client
        assert c.patch("/api/todos/1", json={"title": "x"}).status_code == 401

    def test_delete_todo(self, client):
        c, _ = client
        assert c.delete("/api/todos/1").status_code == 401

    def test_ingest_document(self, client):
        c, _ = client
        assert c.post("/api/rag/ingest", json={"content": "x"}).status_code == 401

    def test_delete_document(self, client):
        c, _ = client
        assert c.delete("/api/rag/documents/1").status_code == 401


# --- Protected endpoints: should return 403 with wrong key ---

class TestProtectedWrongKey:
    H = {"X-API-Key": "wrong-key"}

    def test_create_todo(self, client):
        c, _ = client
        assert c.post("/api/todos/", json={"title": "x"}, headers=self.H).status_code == 403

    def test_update_todo(self, client):
        c, _ = client
        assert c.patch("/api/todos/1", json={"title": "x"}, headers=self.H).status_code == 403

    def test_delete_todo(self, client):
        c, _ = client
        assert c.delete("/api/todos/1", headers=self.H).status_code == 403

    def test_ingest_document(self, client):
        c, _ = client
        assert c.post("/api/rag/ingest", json={"content": "x"}, headers=self.H).status_code == 403

    def test_delete_document(self, client):
        c, _ = client
        assert c.delete("/api/rag/documents/1", headers=self.H).status_code == 403


# --- Protected endpoints: should succeed with valid key ---

class TestProtectedValidKey:
    def test_create_todo(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(
            rows=[(1, "test", None, 0, "2024-01-01", "2024-01-01")]
        )
        assert c.post("/api/todos/", json={"title": "test"}, headers=AUTH_HEADERS).status_code == 201

    def test_update_todo(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(
            rows=[(1, "updated", None, 0, "2024-01-01", "2024-01-01")]
        )
        assert c.patch("/api/todos/1", json={"title": "updated"}, headers=AUTH_HEADERS).status_code == 200

    def test_delete_todo(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        assert c.delete("/api/todos/1", headers=AUTH_HEADERS).status_code == 200

    def test_ingest_document(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        with patch("app.routers.rag.get_embeddings", new_callable=AsyncMock) as mock_emb:
            mock_emb.return_value = [[0.1, 0.2, 0.3]]
            resp = c.post(
                "/api/rag/ingest",
                json={"content": "Some test content for ingestion."},
                headers=AUTH_HEADERS,
            )
        assert resp.status_code == 201

    def test_delete_document(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        assert c.delete("/api/rag/documents/1", headers=AUTH_HEADERS).status_code == 200
