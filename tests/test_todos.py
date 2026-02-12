"""Tests for Todo CRUD endpoints (app/routers/todos.py)."""

import libsql_client

from tests.conftest import AUTH_HEADERS, mock_result


class TestCreateTodo:
    def test_create_with_title_only(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(
            rows=[(1, "Buy groceries", None, 0, "2024-01-01", "2024-01-01")]
        )
        resp = c.post("/api/todos/", json={"title": "Buy groceries"}, headers=AUTH_HEADERS)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Buy groceries"
        assert data["description"] is None
        assert data["completed"] is False

    def test_create_with_title_and_description(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(
            rows=[(1, "Buy groceries", "Milk, eggs", 0, "2024-01-01", "2024-01-01")]
        )
        resp = c.post(
            "/api/todos/",
            json={"title": "Buy groceries", "description": "Milk, eggs"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["description"] == "Milk, eggs"

    def test_create_missing_title_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/todos/", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_create_calls_db_with_correct_sql(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(
            rows=[(1, "test", None, 0, "2024-01-01", "2024-01-01")]
        )
        c.post("/api/todos/", json={"title": "test"}, headers=AUTH_HEADERS)
        call_args = mock_db.execute.call_args[0][0]
        assert isinstance(call_args, libsql_client.Statement)
        assert "INSERT INTO todos" in call_args.sql


class TestListTodos:
    def test_list_empty(self, client):
        c, _ = client
        resp = c.get("/api/todos/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_multiple(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[
            (2, "Second", None, 0, "2024-01-02", "2024-01-02"),
            (1, "First", "desc", 1, "2024-01-01", "2024-01-01"),
        ])
        resp = c.get("/api/todos/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == 2
        assert data[1]["completed"] is True


class TestGetTodo:
    def test_get_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(
            rows=[(1, "Test", "description", 0, "2024-01-01", "2024-01-01")]
        )
        resp = c.get("/api/todos/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert data["title"] == "Test"
        assert data["description"] == "description"

    def test_get_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.get("/api/todos/999")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Todo not found"


class TestUpdateTodo:
    def test_update_title(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(
            rows=[(1, "Updated", None, 0, "2024-01-01", "2024-01-02")]
        )
        resp = c.patch("/api/todos/1", json={"title": "Updated"}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated"

    def test_update_completed(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(
            rows=[(1, "Test", None, 1, "2024-01-01", "2024-01-02")]
        )
        resp = c.patch("/api/todos/1", json={"completed": True}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["completed"] is True

    def test_update_multiple_fields(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(
            rows=[(1, "New title", "New desc", 1, "2024-01-01", "2024-01-02")]
        )
        resp = c.patch(
            "/api/todos/1",
            json={"title": "New title", "description": "New desc", "completed": True},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "New title"
        assert data["description"] == "New desc"
        assert data["completed"] is True

    def test_update_empty_body_returns_400(self, client):
        c, _ = client
        resp = c.patch("/api/todos/1", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 400
        assert "No fields to update" in resp.json()["detail"]

    def test_update_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.patch("/api/todos/999", json={"title": "x"}, headers=AUTH_HEADERS)
        assert resp.status_code == 404


class TestDeleteTodo:
    def test_delete_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        resp = c.delete("/api/todos/1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["message"] == "deleted"

    def test_delete_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.delete("/api/todos/999", headers=AUTH_HEADERS)
        assert resp.status_code == 404
