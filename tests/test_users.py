"""Tests for User Register/Login endpoints (app/routers/users.py)."""

from unittest.mock import patch

import libsql_client

from tests.conftest import AUTH_HEADERS, mock_result


class TestRegister:
    def test_register_success(self, client):
        c, mock_db = client
        # First call: check email exists (no rows), second call: INSERT
        mock_db.execute.side_effect = [
            mock_result(rows=[]),
            mock_result(rows=[(1, "test@example.com", None, "user", "2024-01-01")]),
        ]
        with patch("app.routers.users._hash_password", return_value="hashed"):
            resp = c.post(
                "/api/users/register",
                json={"email": "test@example.com", "password": "mypassword"},
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["id"] == 1
        assert data["organization_id"] is None
        assert data["role"] == "user"
        assert "password" not in data

    def test_register_duplicate_email_returns_409(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        resp = c.post(
            "/api/users/register",
            json={"email": "test@example.com", "password": "mypassword"},
        )
        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"]

    def test_register_missing_fields_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/users/register", json={})
        assert resp.status_code == 422
        assert "email" in resp.json()["detail"]
        assert "password" in resp.json()["detail"]

    def test_register_missing_password_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/users/register", json={"email": "test@example.com"})
        assert resp.status_code == 422
        assert "password" in resp.json()["detail"]

    def test_register_missing_email_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/users/register", json={"password": "mypassword"})
        assert resp.status_code == 422
        assert "email" in resp.json()["detail"]

    def test_register_invalid_org_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.post(
            "/api/users/register",
            json={"email": "test@example.com", "password": "mypassword", "organization_id": 999},
        )
        assert resp.status_code == 404
        assert "Organization not found" in resp.json()["detail"]

    def test_register_calls_db_with_correct_sql(self, client):
        c, mock_db = client
        mock_db.execute.side_effect = [
            mock_result(rows=[]),
            mock_result(rows=[(1, "test@example.com", None, "user", "2024-01-01")]),
        ]
        with patch("app.routers.users._hash_password", return_value="hashed"):
            c.post(
                "/api/users/register",
                json={"email": "test@example.com", "password": "mypassword"},
            )
        # Second call should be the INSERT
        call_args = mock_db.execute.call_args_list[1][0][0]
        assert isinstance(call_args, libsql_client.Statement)
        assert "INSERT INTO users" in call_args.sql


class TestLogin:
    def test_login_success_generates_new_token(self, client):
        c, mock_db = client
        # SELECT user, no valid token found, INSERT new token
        mock_db.execute.side_effect = [
            mock_result(rows=[(1, "hashed")]),
            mock_result(rows=[]),
            mock_result(rows=[("new-token-value", "2024-01-02T00:00:00")]),
        ]
        with patch("app.routers.users._verify_password", return_value=True):
            resp = c.post(
                "/api/users/login",
                json={"email": "test@example.com", "password": "mypassword"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "api_key" in data
        assert "expires_at" in data

    def test_login_reuses_valid_token(self, client):
        c, mock_db = client
        # SELECT user, existing valid token found
        mock_db.execute.side_effect = [
            mock_result(rows=[(1, "hashed")]),
            mock_result(rows=[("existing-token", "2099-01-01T00:00:00")]),
        ]
        with patch("app.routers.users._verify_password", return_value=True):
            resp = c.post(
                "/api/users/login",
                json={"email": "test@example.com", "password": "mypassword"},
            )
        assert resp.status_code == 200
        assert resp.json()["api_key"] == "existing-token"

    def test_login_creates_new_token_when_none_valid(self, client):
        c, mock_db = client
        # No valid tokens (expired ones excluded by SQL), INSERT new token
        mock_db.execute.side_effect = [
            mock_result(rows=[(1, "hashed")]),
            mock_result(rows=[]),
            mock_result(rows=[("fresh-token", "2024-06-02T00:00:00")]),
        ]
        with patch("app.routers.users._verify_password", return_value=True):
            resp = c.post(
                "/api/users/login",
                json={"email": "test@example.com", "password": "mypassword"},
            )
        assert resp.status_code == 200
        assert resp.json()["api_key"] == "fresh-token"

    def test_login_wrong_password_returns_401(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1, "hashed")])
        with patch("app.routers.users._verify_password", return_value=False):
            resp = c.post(
                "/api/users/login",
                json={"email": "test@example.com", "password": "wrong"},
            )
        assert resp.status_code == 401
        assert "Invalid email or password" in resp.json()["detail"]

    def test_login_nonexistent_email_returns_401(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.post(
            "/api/users/login",
            json={"email": "nobody@example.com", "password": "pass"},
        )
        assert resp.status_code == 401

    def test_login_missing_fields_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/users/login", json={})
        assert resp.status_code == 422
        assert "email" in resp.json()["detail"]
        assert "password" in resp.json()["detail"]

    def test_login_missing_email_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/users/login", json={"password": "mypassword"})
        assert resp.status_code == 422
        assert "email" in resp.json()["detail"]

    def test_login_missing_password_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/users/login", json={"email": "test@example.com"})
        assert resp.status_code == 422
        assert "password" in resp.json()["detail"]


class TestUpdateUserRole:
    def test_promote_to_admin(self, client):
        c, mock_db = client
        updated_row = (1, "test@example.com", None, "admin", "2024-01-01")
        mock_db.execute.return_value = mock_result(rows=[updated_row])
        resp = c.patch("/api/users/1/role", json={"role": "admin"}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "admin"
        assert data["id"] == 1

    def test_demote_to_user(self, client):
        c, mock_db = client
        updated_row = (1, "test@example.com", None, "user", "2024-01-01")
        mock_db.execute.return_value = mock_result(rows=[updated_row])
        resp = c.patch("/api/users/1/role", json={"role": "user"}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["role"] == "user"

    def test_nonexistent_user_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.patch("/api/users/999/role", json={"role": "admin"}, headers=AUTH_HEADERS)
        assert resp.status_code == 404
        assert "User not found" in resp.json()["detail"]

    def test_missing_role_returns_422(self, client):
        c, _ = client
        resp = c.patch("/api/users/1/role", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 422
        assert "role" in resp.json()["detail"]

    def test_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.patch("/api/users/1/role", json={"role": "admin"})
        assert resp.status_code == 401
