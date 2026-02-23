"""Tests for RAG endpoints (app/routers/rag.py)."""

from unittest.mock import AsyncMock, patch

from tests.conftest import AUTH_HEADERS, mock_result


class TestIngestDocument:
    def test_ingest_success(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        with patch("app.routers.rag.get_embeddings", new_callable=AsyncMock) as mock_emb:
            mock_emb.return_value = [[0.1, 0.2], [0.3, 0.4]]
            resp = c.post(
                "/api/rag/ingest",
                json={"content": "First paragraph.\n\nSecond paragraph.", "title": "Test Doc"},
                headers=AUTH_HEADERS,
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["document_id"] == 1
        assert data["chunks_created"] > 0
        assert data["message"] == "Document ingested successfully"

    def test_ingest_stores_embeddings_in_batch(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        with patch("app.routers.rag.get_embeddings", new_callable=AsyncMock) as mock_emb:
            mock_emb.return_value = [[0.1], [0.2]]
            c.post(
                "/api/rag/ingest",
                json={"content": "Chunk one.\n\nChunk two."},
                headers=AUTH_HEADERS,
            )
        # batch() should be called to store the embeddings
        assert mock_db.batch.called

    def test_ingest_empty_content(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        resp = c.post(
            "/api/rag/ingest",
            json={"content": "   "},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["chunks_created"] == 0

    def test_ingest_default_title(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        with patch("app.routers.rag.get_embeddings", new_callable=AsyncMock) as mock_emb:
            mock_emb.return_value = [[0.1]]
            c.post("/api/rag/ingest", json={"content": "Some text."}, headers=AUTH_HEADERS)
        # First execute call is the INSERT — check the title param
        insert_call = mock_db.execute.call_args_list[0]
        stmt = insert_call[0][0]
        assert stmt.args[0] == "Untitled"

    def test_ingest_missing_content_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/rag/ingest", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 422
        assert "content" in resp.json()["detail"]


class TestQueryDocument:
    def _setup_query_mocks(self, mock_db):
        mock_db.execute.side_effect = [
            mock_result(rows=[(1,)]),  # most recent doc
            mock_result(rows=[
                ("chunk A", '[0.1, 0.2, 0.3]'),
                ("chunk B", '[0.4, 0.5, 0.6]'),
                ("chunk C", '[0.7, 0.8, 0.9]'),
            ]),  # embeddings
        ]

    def test_query_success(self, client):
        c, mock_db = client
        self._setup_query_mocks(mock_db)
        with patch("app.routers.rag.get_embeddings", new_callable=AsyncMock) as mock_emb, \
             patch("app.routers.rag.generate_answer", new_callable=AsyncMock) as mock_gen:
            mock_emb.return_value = [[0.7, 0.8, 0.9]]
            mock_gen.return_value = "The answer is 42."
            resp = c.post("/api/rag/query", json={"question": "What is the answer?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "The answer is 42."
        assert isinstance(data["sources"], list)
        assert len(data["sources"]) > 0

    def test_query_with_explicit_document_id(self, client):
        c, mock_db = client
        mock_db.execute.side_effect = [
            mock_result(rows=[(5,)]),  # document exists
            mock_result(rows=[("chunk", '[0.1, 0.2]')]),  # embeddings
        ]
        with patch("app.routers.rag.get_embeddings", new_callable=AsyncMock) as mock_emb, \
             patch("app.routers.rag.generate_answer", new_callable=AsyncMock) as mock_gen:
            mock_emb.return_value = [[0.1, 0.2]]
            mock_gen.return_value = "Answer"
            resp = c.post("/api/rag/query", json={"question": "?", "document_id": 5})
        assert resp.status_code == 200

    def test_query_no_documents_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.post("/api/rag/query", json={"question": "?"})
        assert resp.status_code == 404
        assert "No documents found" in resp.json()["detail"]

    def test_query_nonexistent_document_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.post("/api/rag/query", json={"question": "?", "document_id": 999})
        assert resp.status_code == 404

    def test_query_no_embeddings_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.side_effect = [
            mock_result(rows=[(1,)]),  # doc exists
            mock_result(rows=[]),  # no embeddings
        ]
        resp = c.post("/api/rag/query", json={"question": "?"})
        assert resp.status_code == 404
        assert "No embeddings" in resp.json()["detail"]

    def test_query_missing_question_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/rag/query", json={})
        assert resp.status_code == 422
        assert "question" in resp.json()["detail"]


class TestListDocuments:
    def test_list_empty(self, client):
        c, _ = client
        resp = c.get("/api/rag/documents")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_multiple(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[
            (2, "Doc B", "2024-01-02"),
            (1, "Doc A", "2024-01-01"),
        ])
        resp = c.get("/api/rag/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == 2
        assert data[1]["title"] == "Doc A"


class TestDeleteDocument:
    def test_delete_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        resp = c.delete("/api/rag/documents/1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["message"] == "deleted"
        # Should have called execute twice (delete embeddings, then delete document)
        assert mock_db.execute.call_count == 2

    def test_delete_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.delete("/api/rag/documents/999", headers=AUTH_HEADERS)
        assert resp.status_code == 404
