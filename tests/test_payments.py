"""Tests for Payment CRUD endpoints (app/routers/payments.py)."""

import libsql_client

from tests.conftest import AUTH_HEADERS, mock_result

# columns: id, date, expenses, tags, created_at, updated_at
PAYMENT_ROW = (1, "2024-01-15", '[1, 2]', '[3]', "2024-01-15", "2024-01-15")


class TestCreatePayment:
    def test_create_full(self, client):
        c, mock_db = client
        # expense validation → tag validation → INSERT
        mock_db.execute.side_effect = [
            mock_result(rows=[(1,), (2,)]),   # expense IDs found
            mock_result(rows=[(3,)]),          # tag IDs found
            mock_result(rows=[PAYMENT_ROW]),   # INSERT result
        ]
        resp = c.post(
            "/api/payments/",
            json={"date": "2024-01-15", "expense_ids": [1, 2], "tag_ids": [3]},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["date"] == "2024-01-15"
        assert data["expense_ids"] == [1, 2]
        assert data["tag_ids"] == [3]

    def test_create_minimal(self, client):
        c, mock_db = client
        row = (2, "2024-02-01", None, None, "2024-02-01", "2024-02-01")
        mock_db.execute.return_value = mock_result(rows=[row])
        resp = c.post(
            "/api/payments/",
            json={"date": "2024-02-01"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["date"] == "2024-02-01"
        assert data["expense_ids"] is None
        assert data["tag_ids"] is None

    def test_create_missing_date_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/payments/", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 422
        assert "date" in resp.json()["detail"]

    def test_create_invalid_expense_returns_404(self, client):
        c, mock_db = client
        # expense IDs [999] not found — returns empty
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.post(
            "/api/payments/",
            json={"date": "2024-01-15", "expense_ids": [999]},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 404
        assert "Expenses not found" in resp.json()["detail"]

    def test_create_invalid_tag_returns_404(self, client):
        c, mock_db = client
        # expense validation passes, tag not found
        mock_db.execute.side_effect = [
            mock_result(rows=[(1,)]),   # expense IDs found
            mock_result(rows=[]),       # tag IDs not found
        ]
        resp = c.post(
            "/api/payments/",
            json={"date": "2024-01-15", "expense_ids": [1], "tag_ids": [999]},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 404
        assert "Tags not found" in resp.json()["detail"]

    def test_create_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.post("/api/payments/", json={"date": "2024-01-15"})
        assert resp.status_code == 401

    def test_create_calls_db_with_correct_sql(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[PAYMENT_ROW])
        c.post("/api/payments/", json={"date": "2024-01-15"}, headers=AUTH_HEADERS)
        call_args = mock_db.execute.call_args[0][0]
        assert isinstance(call_args, libsql_client.Statement)
        assert "INSERT INTO payments" in call_args.sql


class TestListPayments:
    def test_list_empty(self, client):
        c, _ = client
        resp = c.get("/api/payments/", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_multiple(self, client):
        c, mock_db = client
        row2 = (2, "2024-02-01", None, None, "2024-02-01", "2024-02-01")
        mock_db.execute.return_value = mock_result(rows=[PAYMENT_ROW, row2])
        resp = c.get("/api/payments/", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == 1

    def test_list_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.get("/api/payments/")
        assert resp.status_code == 401


class TestGetPayment:
    def test_get_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[PAYMENT_ROW])
        resp = c.get("/api/payments/1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert data["date"] == "2024-01-15"
        assert data["expense_ids"] == [1, 2]
        assert data["tag_ids"] == [3]

    def test_get_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.get("/api/payments/999", headers=AUTH_HEADERS)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Payment not found"

    def test_get_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.get("/api/payments/1")
        assert resp.status_code == 401


class TestUpdatePayment:
    def test_update_date(self, client):
        c, mock_db = client
        updated_row = (1, "2024-03-01", '[1, 2]', '[3]', "2024-01-15", "2024-03-01")
        mock_db.execute.return_value = mock_result(rows=[updated_row])
        resp = c.patch(
            "/api/payments/1", json={"date": "2024-03-01"}, headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        assert resp.json()["date"] == "2024-03-01"

    def test_update_expense_ids(self, client):
        c, mock_db = client
        updated_row = (1, "2024-01-15", '[1]', '[3]', "2024-01-15", "2024-01-16")
        mock_db.execute.side_effect = [
            mock_result(rows=[(1,)]),        # expense validation
            mock_result(rows=[updated_row]), # UPDATE result
        ]
        resp = c.patch(
            "/api/payments/1", json={"expense_ids": [1]}, headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        assert resp.json()["expense_ids"] == [1]

    def test_update_invalid_tag_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.patch(
            "/api/payments/1", json={"tag_ids": [999]}, headers=AUTH_HEADERS
        )
        assert resp.status_code == 404
        assert "Tags not found" in resp.json()["detail"]

    def test_update_empty_body_returns_400(self, client):
        c, _ = client
        resp = c.patch("/api/payments/1", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 400
        assert "No fields to update" in resp.json()["detail"]

    def test_update_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.patch(
            "/api/payments/999", json={"date": "2024-01-01"}, headers=AUTH_HEADERS
        )
        assert resp.status_code == 404

    def test_update_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.patch("/api/payments/1", json={"date": "2024-01-01"})
        assert resp.status_code == 401


class TestDeletePayment:
    def test_delete_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        resp = c.delete("/api/payments/1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["message"] == "deleted"

    def test_delete_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.delete("/api/payments/999", headers=AUTH_HEADERS)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Payment not found"

    def test_delete_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.delete("/api/payments/1")
        assert resp.status_code == 401
