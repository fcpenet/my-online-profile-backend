"""Tests for Trip CRUD endpoints (app/routers/trips.py)."""

import libsql_client

from tests.conftest import AUTH_HEADERS, mock_result

# columns: id, title, description, start_date, end_date,
#          participants, created_at, updated_at
TRIP_ROW = (1, "Europe 2024", "Summer trip", "2024-06-01", "2024-06-15",
            '[1, 2]', "2024-01-01", "2024-01-01")


class TestCreateTrip:
    def test_create_full(self, client):
        c, mock_db = client
        # First call: _validate_participants; second: INSERT
        mock_db.execute.side_effect = [
            mock_result(rows=[(1,), (2,)]),  # both users exist
            mock_result(rows=[TRIP_ROW]),
        ]
        resp = c.post(
            "/api/trips/",
            json={
                "title": "Europe 2024",
                "description": "Summer trip",
                "start_date": "2024-06-01",
                "end_date": "2024-06-15",
                "participants": [1, 2],
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Europe 2024"
        assert data["start_date"] == "2024-06-01"
        assert data["participants"] == [1, 2]

    def test_create_with_participants_validates_users(self, client):
        c, mock_db = client
        # First call: _validate_participants; second: INSERT
        mock_db.execute.side_effect = [
            mock_result(rows=[(1,), (2,)]),  # both users exist
            mock_result(rows=[TRIP_ROW]),
        ]
        resp = c.post(
            "/api/trips/",
            json={"title": "Trip", "participants": [1, 2]},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["participants"] == [1, 2]

    def test_create_invalid_participant_returns_404(self, client):
        c, mock_db = client
        # Validation returns only 1 of 2 requested users
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        resp = c.post(
            "/api/trips/",
            json={"title": "Trip", "participants": [1, 999]},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 404
        assert "Users not found" in resp.json()["detail"]

    def test_create_minimal_no_participants(self, client):
        c, mock_db = client
        row = (2, "Weekend Trip", None, None, None, None, "2024-01-01", "2024-01-01")
        mock_db.execute.return_value = mock_result(rows=[row])
        resp = c.post("/api/trips/", json={"title": "Weekend Trip"}, headers=AUTH_HEADERS)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Weekend Trip"
        assert data["participants"] is None

    def test_create_missing_title_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/trips/", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_create_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.post("/api/trips/", json={"title": "Test"})
        assert resp.status_code == 401

    def test_create_calls_db_with_correct_sql(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[TRIP_ROW])
        c.post("/api/trips/", json={"title": "Europe 2024"}, headers=AUTH_HEADERS)
        call_args = mock_db.execute.call_args[0][0]
        assert isinstance(call_args, libsql_client.Statement)
        assert "INSERT INTO trips" in call_args.sql


class TestListTrips:
    def test_list_empty(self, client):
        c, _ = client
        resp = c.get("/api/trips/", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_multiple(self, client):
        c, mock_db = client
        row2 = (2, "Asia Trip", None, "2024-09-01", "2024-09-14",
                None, "2024-02-01", "2024-02-01")
        mock_db.execute.return_value = mock_result(rows=[row2, TRIP_ROW])
        resp = c.get("/api/trips/", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == 2

    def test_list_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.get("/api/trips/")
        assert resp.status_code == 401


class TestGetTrip:
    def test_get_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[TRIP_ROW])
        resp = c.get("/api/trips/1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert data["title"] == "Europe 2024"
        assert data["participants"] == [1, 2]

    def test_get_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.get("/api/trips/999", headers=AUTH_HEADERS)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Trip not found"

    def test_get_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.get("/api/trips/1")
        assert resp.status_code == 401


class TestUpdateTrip:
    def test_update_title(self, client):
        c, mock_db = client
        updated = (1, "Europe 2025", "Summer trip", "2024-06-01", "2024-06-15",
                   '[1, 2]', "2024-01-01", "2024-01-02")
        mock_db.execute.return_value = mock_result(rows=[updated])
        resp = c.patch("/api/trips/1", json={"title": "Europe 2025"}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Europe 2025"

    def test_update_participants_validates_users(self, client):
        c, mock_db = client
        updated = (1, "Europe 2024", "Summer trip", "2024-06-01", "2024-06-15",
                   '[1, 3]', "2024-01-01", "2024-01-02")
        mock_db.execute.side_effect = [
            mock_result(rows=[(1,), (3,)]),  # both users exist
            mock_result(rows=[updated]),
        ]
        resp = c.patch(
            "/api/trips/1", json={"participants": [1, 3]}, headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        assert resp.json()["participants"] == [1, 3]

    def test_update_invalid_participant_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.patch(
            "/api/trips/1", json={"participants": [999]}, headers=AUTH_HEADERS
        )
        assert resp.status_code == 404
        assert "Users not found" in resp.json()["detail"]

    def test_update_dates(self, client):
        c, mock_db = client
        updated = (1, "Europe 2024", "Summer trip", "2024-07-01", "2024-07-15",
                   '[1, 2]', "2024-01-01", "2024-01-02")
        mock_db.execute.return_value = mock_result(rows=[updated])
        resp = c.patch(
            "/api/trips/1",
            json={"start_date": "2024-07-01", "end_date": "2024-07-15"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["start_date"] == "2024-07-01"

    def test_update_empty_body_returns_400(self, client):
        c, _ = client
        resp = c.patch("/api/trips/1", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 400

    def test_update_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.patch("/api/trips/999", json={"title": "x"}, headers=AUTH_HEADERS)
        assert resp.status_code == 404


class TestDeleteTrip:
    def test_delete_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        resp = c.delete("/api/trips/1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["message"] == "deleted"

    def test_delete_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.delete("/api/trips/999", headers=AUTH_HEADERS)
        assert resp.status_code == 404

    def test_delete_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.delete("/api/trips/1")
        assert resp.status_code == 401
