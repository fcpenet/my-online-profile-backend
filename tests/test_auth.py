import os
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Set env vars before importing the app
os.environ.setdefault("API_KEY", "test-secret-key")
os.environ.setdefault("TURSO_DATABASE_URL", "https://fake-db.turso.io")
os.environ.setdefault("TURSO_AUTH_TOKEN", "fake-token")
os.environ.setdefault("OPENAI_API_KEY", "sk-fake-key")

TEST_API_KEY = os.environ["API_KEY"]


def _mock_result(rows=None):
    result = MagicMock()
    result.rows = rows or []
    return result


@pytest.fixture
def client():
    """Create a TestClient with all database calls mocked."""
    mock_db = AsyncMock()
    mock_db.execute.return_value = _mock_result()
    mock_db.batch.return_value = []

    # Patch at every usage site (modules bind references on import)
    with patch("app.routers.todos.get_client", return_value=mock_db), \
         patch("app.routers.rag.get_client", return_value=mock_db), \
         patch("app.init_db", new_callable=AsyncMock):
        from app import app
        with TestClient(app) as c:
            yield c, mock_db


# --- Public endpoints: should work without any API key ---

class TestPublicEndpoints:
    def test_health_no_key(self, client):
        c, _ = client
        resp = c.get("/api/health")
        assert resp.status_code == 200

    def test_list_todos_no_key(self, client):
        c, _ = client
        resp = c.get("/api/todos/")
        assert resp.status_code == 200

    def test_get_todo_no_key(self, client):
        c, mock_db = client
        mock_db.execute.return_value = _mock_result(
            rows=[(1, "Test", "desc", 0, "2024-01-01", "2024-01-01")]
        )
        resp = c.get("/api/todos/1")
        assert resp.status_code == 200

    def test_list_documents_no_key(self, client):
        c, _ = client
        resp = c.get("/api/rag/documents")
        assert resp.status_code == 200

    def test_query_document_no_key(self, client):
        """POST /api/rag/query is public — should not return 401/403."""
        c, mock_db = client
        mock_db.execute.side_effect = [
            _mock_result(rows=[(1,)]),  # most recent document
            _mock_result(rows=[("chunk text", '[0.1, 0.2, 0.3]')]),  # embeddings
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
    def test_create_todo_no_key(self, client):
        c, _ = client
        resp = c.post("/api/todos/", json={"title": "test"})
        assert resp.status_code == 401

    def test_update_todo_no_key(self, client):
        c, _ = client
        resp = c.patch("/api/todos/1", json={"title": "updated"})
        assert resp.status_code == 401

    def test_delete_todo_no_key(self, client):
        c, _ = client
        resp = c.delete("/api/todos/1")
        assert resp.status_code == 401

    def test_ingest_document_no_key(self, client):
        c, _ = client
        resp = c.post("/api/rag/ingest", json={"content": "test"})
        assert resp.status_code == 401

    def test_delete_document_no_key(self, client):
        c, _ = client
        resp = c.delete("/api/rag/documents/1")
        assert resp.status_code == 401


# --- Protected endpoints: should return 403 with wrong key ---

class TestProtectedWrongKey:
    HEADERS = {"X-API-Key": "wrong-key"}

    def test_create_todo_wrong_key(self, client):
        c, _ = client
        resp = c.post("/api/todos/", json={"title": "test"}, headers=self.HEADERS)
        assert resp.status_code == 403

    def test_update_todo_wrong_key(self, client):
        c, _ = client
        resp = c.patch("/api/todos/1", json={"title": "updated"}, headers=self.HEADERS)
        assert resp.status_code == 403

    def test_delete_todo_wrong_key(self, client):
        c, _ = client
        resp = c.delete("/api/todos/1", headers=self.HEADERS)
        assert resp.status_code == 403

    def test_ingest_document_wrong_key(self, client):
        c, _ = client
        resp = c.post("/api/rag/ingest", json={"content": "test"}, headers=self.HEADERS)
        assert resp.status_code == 403

    def test_delete_document_wrong_key(self, client):
        c, _ = client
        resp = c.delete("/api/rag/documents/1", headers=self.HEADERS)
        assert resp.status_code == 403


# --- Protected endpoints: should succeed with valid key ---

class TestProtectedValidKey:
    HEADERS = {"X-API-Key": TEST_API_KEY}

    def test_create_todo_valid_key(self, client):
        c, mock_db = client
        mock_db.execute.return_value = _mock_result(
            rows=[(1, "test", None, 0, "2024-01-01", "2024-01-01")]
        )
        resp = c.post("/api/todos/", json={"title": "test"}, headers=self.HEADERS)
        assert resp.status_code == 201

    def test_update_todo_valid_key(self, client):
        c, mock_db = client
        mock_db.execute.return_value = _mock_result(
            rows=[(1, "updated", None, 0, "2024-01-01", "2024-01-01")]
        )
        resp = c.patch("/api/todos/1", json={"title": "updated"}, headers=self.HEADERS)
        assert resp.status_code == 200

    def test_delete_todo_valid_key(self, client):
        c, mock_db = client
        mock_db.execute.return_value = _mock_result(rows=[(1,)])
        resp = c.delete("/api/todos/1", headers=self.HEADERS)
        assert resp.status_code == 200

    def test_ingest_document_valid_key(self, client):
        c, mock_db = client
        mock_db.execute.return_value = _mock_result(rows=[(1,)])
        with patch("app.routers.rag.get_embeddings", new_callable=AsyncMock) as mock_emb:
            mock_emb.return_value = [[0.1, 0.2, 0.3]]
            resp = c.post(
                "/api/rag/ingest",
                json={"content": "Some test content for ingestion."},
                headers=self.HEADERS,
            )
        assert resp.status_code == 201

    def test_delete_document_valid_key(self, client):
        c, mock_db = client
        mock_db.execute.return_value = _mock_result(rows=[(1,)])
        resp = c.delete("/api/rag/documents/1", headers=self.HEADERS)
        assert resp.status_code == 200
