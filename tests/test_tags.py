"""Tests for Tag CRUD endpoints (app/routers/tags.py)."""

import libsql_client

from tests.conftest import AUTH_HEADERS, mock_result

# columns: id, name, created_at
TAG_ROW = (1, "food", "2024-01-01")


class TestCreateTag:
    def test_create(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[TAG_ROW])
        resp = c.post("/api/tags/", json={"name": "food"}, headers=AUTH_HEADERS)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == 1
        assert data["name"] == "food"
        assert data["created_at"] == "2024-01-01"

    def test_create_duplicate_returns_409(self, client):
        c, mock_db = client
        mock_db.execute.side_effect = Exception("UNIQUE constraint failed")
        resp = c.post("/api/tags/", json={"name": "food"}, headers=AUTH_HEADERS)
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    def test_create_missing_name_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/tags/", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 422
        assert "name" in resp.json()["detail"]

    def test_create_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.post("/api/tags/", json={"name": "food"})
        assert resp.status_code == 401

    def test_create_calls_db_with_correct_sql(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[TAG_ROW])
        c.post("/api/tags/", json={"name": "food"}, headers=AUTH_HEADERS)
        call_args = mock_db.execute.call_args[0][0]
        assert isinstance(call_args, libsql_client.Statement)
        assert "INSERT INTO tags" in call_args.sql


class TestListTags:
    def test_list_empty(self, client):
        c, _ = client
        resp = c.get("/api/tags/", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_multiple(self, client):
        c, mock_db = client
        row2 = (2, "travel", "2024-01-02")
        mock_db.execute.return_value = mock_result(rows=[TAG_ROW, row2])
        resp = c.get("/api/tags/", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "food"
        assert data[1]["name"] == "travel"

    def test_list_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.get("/api/tags/")
        assert resp.status_code == 401


class TestGetTag:
    def test_get_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[TAG_ROW])
        resp = c.get("/api/tags/1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert data["name"] == "food"

    def test_get_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.get("/api/tags/999", headers=AUTH_HEADERS)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Tag not found"

    def test_get_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.get("/api/tags/1")
        assert resp.status_code == 401


class TestDeleteTag:
    def test_delete_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        resp = c.delete("/api/tags/1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["message"] == "deleted"

    def test_delete_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.delete("/api/tags/999", headers=AUTH_HEADERS)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Tag not found"

    def test_delete_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.delete("/api/tags/1")
        assert resp.status_code == 401
