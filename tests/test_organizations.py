"""Tests for Organization CRUD endpoints (app/routers/organizations.py)."""

import libsql_client

from tests.conftest import AUTH_HEADERS, mock_result

ORG_ROW = (1, "Acme Corp", "2024-01-01", "2024-01-01")


class TestCreateOrganization:
    def test_create_success(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[ORG_ROW])
        resp = c.post(
            "/api/organizations/",
            json={"name": "Acme Corp"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Acme Corp"
        assert data["id"] == 1

    def test_create_missing_name_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/organizations/", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 422
        assert "name" in resp.json()["detail"]

    def test_create_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.post("/api/organizations/", json={"name": "Test"})
        assert resp.status_code == 401

    def test_create_calls_db_with_correct_sql(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[ORG_ROW])
        c.post("/api/organizations/", json={"name": "Test"}, headers=AUTH_HEADERS)
        call_args = mock_db.execute.call_args[0][0]
        assert isinstance(call_args, libsql_client.Statement)
        assert "INSERT INTO organizations" in call_args.sql


class TestListOrganizations:
    def test_list_empty(self, client):
        c, _ = client
        resp = c.get("/api/organizations/", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_multiple(self, client):
        c, mock_db = client
        row2 = (2, "Other Corp", "2024-01-02", "2024-01-02")
        mock_db.execute.return_value = mock_result(rows=[row2, ORG_ROW])
        resp = c.get("/api/organizations/", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.get("/api/organizations/")
        assert resp.status_code == 401


class TestGetOrganization:
    def test_get_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[ORG_ROW])
        resp = c.get("/api/organizations/1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Acme Corp"

    def test_get_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.get("/api/organizations/999", headers=AUTH_HEADERS)
        assert resp.status_code == 404


class TestUpdateOrganization:
    def test_update_name(self, client):
        c, mock_db = client
        updated = (1, "New Name", "2024-01-01", "2024-01-02")
        mock_db.execute.return_value = mock_result(rows=[updated])
        resp = c.patch(
            "/api/organizations/1", json={"name": "New Name"}, headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_update_empty_body_returns_400(self, client):
        c, _ = client
        resp = c.patch("/api/organizations/1", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 400

    def test_update_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.patch(
            "/api/organizations/999", json={"name": "x"}, headers=AUTH_HEADERS
        )
        assert resp.status_code == 404


class TestDeleteOrganization:
    def test_delete_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        resp = c.delete("/api/organizations/1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["message"] == "deleted"

    def test_delete_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.delete("/api/organizations/999", headers=AUTH_HEADERS)
        assert resp.status_code == 404

    def test_delete_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.delete("/api/organizations/1")
        assert resp.status_code == 401
