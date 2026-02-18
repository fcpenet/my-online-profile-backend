"""Tests for Expense CRUD endpoints (app/routers/expenses.py)."""

import json

import libsql_client

from tests.conftest import AUTH_HEADERS, mock_result

SAMPLE_ROW = (1, "Dinner", 45.99, "meal", "Food", "Restaurant", "Team dinner",
              "Geneva", '["Alice", "Bob"]', "2024-01-01", "2024-01-01")


class TestCreateExpense:
    def test_create_full(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[SAMPLE_ROW])
        resp = c.post(
            "/api/expenses/",
            json={
                "title": "Dinner",
                "amount": 45.99,
                "tag": "meal",
                "category": "Food",
                "location": "Restaurant",
                "description": "Team dinner",
                "paid_by": "Geneva",
                "shared_with": ["Alice", "Bob"],
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Dinner"
        assert data["amount"] == 45.99
        assert data["paid_by"] == "Geneva"
        assert data["shared_with"] == ["Alice", "Bob"]

    def test_create_minimal(self, client):
        c, mock_db = client
        row = (2, "Coffee", 5.0, None, None, None, None, "Geneva", None,
               "2024-01-01", "2024-01-01")
        mock_db.execute.return_value = mock_result(rows=[row])
        resp = c.post(
            "/api/expenses/",
            json={"title": "Coffee", "amount": 5.0, "paid_by": "Geneva"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Coffee"
        assert data["shared_with"] is None
        assert data["tag"] is None

    def test_create_missing_required_fields_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/expenses/", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_create_missing_title_returns_422(self, client):
        c, _ = client
        resp = c.post(
            "/api/expenses/",
            json={"amount": 10.0, "paid_by": "Geneva"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

    def test_create_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.post(
            "/api/expenses/",
            json={"title": "Test", "amount": 10.0, "paid_by": "Geneva"},
        )
        assert resp.status_code == 401

    def test_create_calls_db_with_correct_sql(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[SAMPLE_ROW])
        c.post(
            "/api/expenses/",
            json={"title": "Dinner", "amount": 45.99, "paid_by": "Geneva"},
            headers=AUTH_HEADERS,
        )
        call_args = mock_db.execute.call_args[0][0]
        assert isinstance(call_args, libsql_client.Statement)
        assert "INSERT INTO expenses" in call_args.sql


class TestListExpenses:
    def test_list_empty(self, client):
        c, _ = client
        resp = c.get("/api/expenses/", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_multiple(self, client):
        c, mock_db = client
        row2 = (2, "Lunch", 15.0, None, "Food", None, None, "Bob", None,
                "2024-01-02", "2024-01-02")
        mock_db.execute.return_value = mock_result(rows=[row2, SAMPLE_ROW])
        resp = c.get("/api/expenses/", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == 2

    def test_list_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.get("/api/expenses/")
        assert resp.status_code == 401


class TestGetExpense:
    def test_get_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[SAMPLE_ROW])
        resp = c.get("/api/expenses/1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert data["title"] == "Dinner"
        assert data["amount"] == 45.99

    def test_get_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.get("/api/expenses/999", headers=AUTH_HEADERS)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Expense not found"

    def test_get_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.get("/api/expenses/1")
        assert resp.status_code == 401


class TestUpdateExpense:
    def test_update_amount(self, client):
        c, mock_db = client
        updated_row = (1, "Dinner", 50.0, "meal", "Food", "Restaurant",
                       "Team dinner", "Geneva", '["Alice", "Bob"]',
                       "2024-01-01", "2024-01-02")
        mock_db.execute.return_value = mock_result(rows=[updated_row])
        resp = c.patch(
            "/api/expenses/1", json={"amount": 50.0}, headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        assert resp.json()["amount"] == 50.0

    def test_update_shared_with(self, client):
        c, mock_db = client
        updated_row = (1, "Dinner", 45.99, "meal", "Food", "Restaurant",
                       "Team dinner", "Geneva", '["Alice", "Bob", "Charlie"]',
                       "2024-01-01", "2024-01-02")
        mock_db.execute.return_value = mock_result(rows=[updated_row])
        resp = c.patch(
            "/api/expenses/1",
            json={"shared_with": ["Alice", "Bob", "Charlie"]},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["shared_with"] == ["Alice", "Bob", "Charlie"]

    def test_update_empty_body_returns_400(self, client):
        c, _ = client
        resp = c.patch("/api/expenses/1", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 400
        assert "No fields to update" in resp.json()["detail"]

    def test_update_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.patch(
            "/api/expenses/999", json={"amount": 10.0}, headers=AUTH_HEADERS
        )
        assert resp.status_code == 404


class TestDeleteExpense:
    def test_delete_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        resp = c.delete("/api/expenses/1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["message"] == "deleted"

    def test_delete_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.delete("/api/expenses/999", headers=AUTH_HEADERS)
        assert resp.status_code == 404

    def test_delete_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.delete("/api/expenses/1")
        assert resp.status_code == 401
