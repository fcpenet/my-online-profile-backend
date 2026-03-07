"""Tests for Token endpoints (app/routers/tokens.py)."""

import libsql_client

from tests.conftest import AUTH_HEADERS, mock_result

# columns: id, token, max_uses, uses, expires_at, created_at, user_id
TOKEN_ROW = (1, "abc123tokenvalue", 5, 2, None, "2024-01-01", None)

# validate query adds a 7th column: not_expired (1=True, 0=False)
# (does not include user_id — custom SELECT)
VALIDATE_ROW = (1, "abc123tokenvalue", 5, 2, None, "2024-01-01", 1)


class TestCreateToken:
    def test_create_minimal(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[TOKEN_ROW])
        resp = c.post("/api/tokens/", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == 1
        assert data["token"] == "abc123tokenvalue"
        assert data["max_uses"] == 5
        assert data["uses"] == 2
        assert data["expires_at"] is None
        assert data["user_id"] is None

    def test_create_with_options(self, client):
        c, mock_db = client
        row = (2, "newtoken", 10, 0, "2099-01-01", "2024-01-01", None)
        mock_db.execute.return_value = mock_result(rows=[row])
        resp = c.post(
            "/api/tokens/",
            json={"max_uses": 10, "expires_at": "2099-01-01"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["max_uses"] == 10
        assert data["expires_at"] == "2099-01-01"

    def test_create_with_user_id(self, client):
        c, mock_db = client
        row = (3, "usertoken", 1, 0, None, "2024-01-01", 42)
        mock_db.execute.side_effect = [
            mock_result(rows=[(42,)]),   # user validation
            mock_result(rows=[row]),     # INSERT result
        ]
        resp = c.post(
            "/api/tokens/",
            json={"user_id": 42},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["user_id"] == 42

    def test_create_invalid_user_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.post(
            "/api/tokens/",
            json={"user_id": 999},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 404
        assert "User not found" in resp.json()["detail"]

    def test_create_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.post("/api/tokens/", json={})
        assert resp.status_code == 401

    def test_create_calls_db_with_correct_sql(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[TOKEN_ROW])
        c.post("/api/tokens/", json={}, headers=AUTH_HEADERS)
        call_args = mock_db.execute.call_args[0][0]
        assert isinstance(call_args, libsql_client.Statement)
        assert "INSERT INTO tokens" in call_args.sql


class TestListTokens:
    def test_list_empty(self, client):
        c, _ = client
        resp = c.get("/api/tokens/", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_multiple(self, client):
        c, mock_db = client
        row2 = (2, "anothertoken", 1, 0, None, "2024-01-02", None)
        mock_db.execute.return_value = mock_result(rows=[TOKEN_ROW, row2])
        resp = c.get("/api/tokens/", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == 1
        assert data[1]["id"] == 2

    def test_list_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.get("/api/tokens/")
        assert resp.status_code == 401


class TestGetToken:
    def test_get_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[TOKEN_ROW])
        resp = c.get("/api/tokens/1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert data["token"] == "abc123tokenvalue"

    def test_get_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.get("/api/tokens/999", headers=AUTH_HEADERS)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Token not found"

    def test_get_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.get("/api/tokens/1")
        assert resp.status_code == 401


class TestValidateToken:
    def test_validate_valid_token(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[VALIDATE_ROW])
        resp = c.get("/api/tokens/validate/abc123tokenvalue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["uses_remaining"] == 3  # max_uses=5, uses=2
        assert data["expires_at"] is None

    def test_validate_nonexistent_token_returns_invalid(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.get("/api/tokens/validate/nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["uses_remaining"] is None
        assert data["expires_at"] is None

    def test_validate_exhausted_token_returns_invalid(self, client):
        c, mock_db = client
        # max_uses=5, uses=5 — exhausted, not_expired=1
        exhausted_row = (1, "abc123tokenvalue", 5, 5, None, "2024-01-01", 1)
        mock_db.execute.return_value = mock_result(rows=[exhausted_row])
        resp = c.get("/api/tokens/validate/abc123tokenvalue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["uses_remaining"] == 0

    def test_validate_expired_token_returns_invalid(self, client):
        c, mock_db = client
        # not_expired=0
        expired_row = (1, "abc123tokenvalue", 5, 2, "2020-01-01", "2024-01-01", 0)
        mock_db.execute.return_value = mock_result(rows=[expired_row])
        resp = c.get("/api/tokens/validate/abc123tokenvalue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False

    def test_validate_unlimited_token(self, client):
        c, mock_db = client
        # max_uses=0 means unlimited
        unlimited_row = (1, "abc123tokenvalue", 0, 100, None, "2024-01-01", 1)
        mock_db.execute.return_value = mock_result(rows=[unlimited_row])
        resp = c.get("/api/tokens/validate/abc123tokenvalue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["uses_remaining"] is None


class TestUseToken:
    def test_use_existing_token(self, client):
        c, mock_db = client
        updated_row = (1, "abc123tokenvalue", 5, 3, None, "2024-01-01", None)
        mock_db.execute.side_effect = [
            mock_result(rows=[TOKEN_ROW]),   # SELECT token
            mock_result(rows=[updated_row]), # UPDATE uses
        ]
        resp = c.post("/api/tokens/use/abc123tokenvalue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["uses"] == 3

    def test_use_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.post("/api/tokens/use/nonexistent")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Token not found"

    def test_use_exhausted_returns_410(self, client):
        c, mock_db = client
        exhausted_row = (1, "abc123tokenvalue", 5, 5, None, "2024-01-01", None)
        mock_db.execute.return_value = mock_result(rows=[exhausted_row])
        resp = c.post("/api/tokens/use/abc123tokenvalue")
        assert resp.status_code == 410
        assert "no uses remaining" in resp.json()["detail"]

    def test_use_expired_returns_410(self, client):
        c, mock_db = client
        expired_row = (1, "abc123tokenvalue", 5, 2, "2020-01-01 00:00:00", "2024-01-01", None)
        now_result = mock_result(rows=[("2025-01-01 00:00:00",)])
        mock_db.execute.side_effect = [
            mock_result(rows=[expired_row]),  # SELECT token
            now_result,                        # SELECT datetime('now')
        ]
        resp = c.post("/api/tokens/use/abc123tokenvalue")
        assert resp.status_code == 410
        assert "expired" in resp.json()["detail"]

    def test_use_unlimited_token(self, client):
        c, mock_db = client
        unlimited_row = (1, "abc123tokenvalue", 0, 50, None, "2024-01-01", None)
        updated_row = (1, "abc123tokenvalue", 0, 51, None, "2024-01-01", None)
        mock_db.execute.side_effect = [
            mock_result(rows=[unlimited_row]),  # SELECT token
            mock_result(rows=[updated_row]),    # UPDATE uses
        ]
        resp = c.post("/api/tokens/use/abc123tokenvalue")
        assert resp.status_code == 200
        assert resp.json()["uses"] == 51


class TestDeleteToken:
    def test_delete_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        resp = c.delete("/api/tokens/1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["message"] == "deleted"

    def test_delete_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.delete("/api/tokens/999", headers=AUTH_HEADERS)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Token not found"

    def test_delete_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.delete("/api/tokens/1")
        assert resp.status_code == 401
