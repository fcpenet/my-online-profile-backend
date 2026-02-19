"""Tests for User Register/Login endpoints (app/routers/users.py)."""

from unittest.mock import patch

import libsql_client

from tests.conftest import mock_result


class TestRegister:
    def test_register_success(self, client):
        c, mock_db = client
        # First call: check email exists (no rows), second call: INSERT
        mock_db.execute.side_effect = [
            mock_result(rows=[]),
            mock_result(rows=[(1, "test@example.com", "2024-01-01")]),
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

    def test_register_missing_password_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/users/register", json={"email": "test@example.com"})
        assert resp.status_code == 422

    def test_register_calls_db_with_correct_sql(self, client):
        c, mock_db = client
        mock_db.execute.side_effect = [
            mock_result(rows=[]),
            mock_result(rows=[(1, "test@example.com", "2024-01-01")]),
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
    def test_login_success_generates_new_key(self, client):
        c, mock_db = client
        # First call: SELECT user (no existing key), second: UPDATE RETURNING expires_at
        mock_db.execute.side_effect = [
            mock_result(rows=[(1, "hashed", None, None)]),
            mock_result(rows=[("2024-01-02T00:00:00",)]),
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

    def test_login_reuses_valid_key(self, client):
        c, mock_db = client
        # User has a valid key (expires in future)
        mock_db.execute.side_effect = [
            mock_result(rows=[(1, "hashed", "existing-key", "2099-01-01T00:00:00")]),
            mock_result(rows=[("2024-01-01T00:00:00",)]),  # now < expires_at
        ]
        with patch("app.routers.users._verify_password", return_value=True):
            resp = c.post(
                "/api/users/login",
                json={"email": "test@example.com", "password": "mypassword"},
            )
        assert resp.status_code == 200
        assert resp.json()["api_key"] == "existing-key"

    def test_login_generates_new_key_when_expired(self, client):
        c, mock_db = client
        # User has an expired key
        mock_db.execute.side_effect = [
            mock_result(rows=[(1, "hashed", "old-key", "2020-01-01T00:00:00")]),
            mock_result(rows=[("2024-06-01T00:00:00",)]),  # now > expires_at
            mock_result(rows=[("2024-06-02T00:00:00",)]),  # UPDATE RETURNING expires_at
        ]
        with patch("app.routers.users._verify_password", return_value=True):
            resp = c.post(
                "/api/users/login",
                json={"email": "test@example.com", "password": "mypassword"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["api_key"] != "old-key"

    def test_login_wrong_password_returns_401(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(
            rows=[(1, "hashed", None, None)]
        )
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
