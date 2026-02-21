"""Tests for Expense CRUD endpoints (app/routers/expenses.py)."""

import libsql_client

from tests.conftest import AUTH_HEADERS, mock_result

# columns: id, title, amount, tag, category, location, description,
#          payor_id, participants, trip_id, created_at, updated_at
SAMPLE_ROW = (1, "Dinner", 45.99, "meal", "Food", "Restaurant", "Team dinner",
              1, '[1, 2]', 2, "2024-01-01", "2024-01-01")


class TestCreateExpense:
    def test_create_full(self, client):
        c, mock_db = client
        # payor check → trip participants check → INSERT
        mock_db.execute.side_effect = [
            mock_result(rows=[(1,)]),          # payor exists
            mock_result(rows=[('[1, 2]',)]),   # trip participants
            mock_result(rows=[SAMPLE_ROW]),    # INSERT result
        ]
        resp = c.post(
            "/api/expenses/",
            json={
                "title": "Dinner",
                "amount": 45.99,
                "tag": "meal",
                "category": "Food",
                "location": "Restaurant",
                "description": "Team dinner",
                "payor_id": 1,
                "participants": [1, 2],
                "trip_id": 2,
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Dinner"
        assert data["amount"] == 45.99
        assert data["payor_id"] == 1
        assert data["participants"] == [1, 2]
        assert data["trip_id"] == 2

    def test_create_minimal(self, client):
        c, mock_db = client
        row = (2, "Coffee", 5.0, None, None, None, None, None, None, None,
               "2024-01-01", "2024-01-01")
        mock_db.execute.return_value = mock_result(rows=[row])
        resp = c.post(
            "/api/expenses/",
            json={"title": "Coffee", "amount": 5.0},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Coffee"
        assert data["participants"] is None
        assert data["payor_id"] is None
        assert data["trip_id"] is None

    def test_create_missing_required_fields_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/expenses/", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_create_missing_title_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/expenses/", json={"amount": 10.0}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_create_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.post("/api/expenses/", json={"title": "Test", "amount": 10.0})
        assert resp.status_code == 401

    def test_create_invalid_payor_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.post(
            "/api/expenses/",
            json={"title": "Dinner", "amount": 45.99, "payor_id": 999},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 404
        assert "Payor not found" in resp.json()["detail"]

    def test_create_invalid_trip_returns_404(self, client):
        c, mock_db = client
        # payor check passes, trip check fails
        mock_db.execute.side_effect = [
            mock_result(rows=[(1,)]),  # user exists
            mock_result(rows=[]),      # trip not found
        ]
        resp = c.post(
            "/api/expenses/",
            json={"title": "Dinner", "amount": 45.99, "payor_id": 1, "trip_id": 999},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 404
        assert "Trip not found" in resp.json()["detail"]

    def test_create_participants_not_in_trip_returns_404(self, client):
        c, mock_db = client
        # no payor; trip participants = [1, 2]; expense participant 999 not in trip
        mock_db.execute.return_value = mock_result(rows=[('[1, 2]',)])
        resp = c.post(
            "/api/expenses/",
            json={"title": "Dinner", "amount": 45.99, "participants": [999], "trip_id": 2},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 404
        assert "Participants not in trip" in resp.json()["detail"]

    def test_create_participants_without_trip_returns_400(self, client):
        c, _ = client
        resp = c.post(
            "/api/expenses/",
            json={"title": "Dinner", "amount": 45.99, "participants": [1]},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 400
        assert "trip_id required" in resp.json()["detail"]

    def test_create_calls_db_with_correct_sql(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[SAMPLE_ROW])
        c.post(
            "/api/expenses/",
            json={"title": "Dinner", "amount": 45.99},
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
        row2 = (2, "Lunch", 15.0, None, "Food", None, None, None, None, None,
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
                       "Team dinner", 1, '[1, 2]', 2,
                       "2024-01-01", "2024-01-02")
        mock_db.execute.return_value = mock_result(rows=[updated_row])
        resp = c.patch("/api/expenses/1", json={"amount": 50.0}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["amount"] == 50.0

    def test_update_participants(self, client):
        c, mock_db = client
        updated_row = (1, "Dinner", 45.99, "meal", "Food", "Restaurant",
                       "Team dinner", 1, '[1, 2, 3]', 2,
                       "2024-01-01", "2024-01-02")
        mock_db.execute.side_effect = [
            mock_result(rows=[(2,)]),            # expense's current trip_id
            mock_result(rows=[('[1, 2, 3]',)]),  # trip's participants
            mock_result(rows=[updated_row]),     # UPDATE result
        ]
        resp = c.patch(
            "/api/expenses/1",
            json={"participants": [1, 2, 3]},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["participants"] == [1, 2, 3]

    def test_update_invalid_payor_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.patch("/api/expenses/1", json={"payor_id": 999}, headers=AUTH_HEADERS)
        assert resp.status_code == 404
        assert "Payor not found" in resp.json()["detail"]

    def test_update_invalid_trip_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.patch("/api/expenses/1", json={"trip_id": 999}, headers=AUTH_HEADERS)
        assert resp.status_code == 404
        assert "Trip not found" in resp.json()["detail"]

    def test_update_participants_not_in_trip_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.side_effect = [
            mock_result(rows=[(2,)]),         # expense's current trip_id
            mock_result(rows=[('[1, 2]',)]),  # trip's participants
        ]
        resp = c.patch(
            "/api/expenses/1",
            json={"participants": [999]},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 404
        assert "Participants not in trip" in resp.json()["detail"]

    def test_update_empty_body_returns_400(self, client):
        c, _ = client
        resp = c.patch("/api/expenses/1", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 400
        assert "No fields to update" in resp.json()["detail"]

    def test_update_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.patch("/api/expenses/999", json={"amount": 10.0}, headers=AUTH_HEADERS)
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
