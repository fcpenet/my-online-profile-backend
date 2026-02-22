"""Tests for Invite management endpoints (app/routers/invites.py)."""

from unittest.mock import patch, AsyncMock

import libsql_client

from tests.conftest import AUTH_HEADERS, mock_result

# columns: id, code, max_uses, uses, created_at
INVITE_ROW = (1, "abc123", 5, 0, "2024-01-01")

# A user API key (not the settings key) — used to test that user keys are rejected
USER_API_KEY_HEADERS = {"X-API-Key": "user-api-key"}


def _mock_user_key_auth():
    """Patches auth so that USER_API_KEY_HEADERS resolves to a real user (not settings key)."""
    async def _get_api_key_returns_different():
        return "settings-key-value"  # different from "user-api-key"

    return patch("app.auth.get_api_key", side_effect=_get_api_key_returns_different)


class TestCreateInvite:
    def test_create_with_explicit_code(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[INVITE_ROW])
        resp = c.post(
            "/api/invites/",
            json={"code": "abc123", "max_uses": 5},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["code"] == "abc123"
        assert data["max_uses"] == 5
        assert data["uses"] == 0

    def test_create_auto_generates_code(self, client):
        c, mock_db = client
        auto_row = (2, "auto-generated", 3, 0, "2024-01-01")
        mock_db.execute.return_value = mock_result(rows=[auto_row])
        resp = c.post(
            "/api/invites/",
            json={"max_uses": 3},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["code"]) > 0
        assert data["max_uses"] == 3

    def test_create_duplicate_code_returns_409(self, client):
        c, mock_db = client
        mock_db.execute.side_effect = Exception("UNIQUE constraint failed")
        resp = c.post(
            "/api/invites/",
            json={"code": "duplicate"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    def test_create_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.post("/api/invites/", json={"max_uses": 1})
        assert resp.status_code == 401

    def test_create_with_user_key_returns_403(self, client):
        c, mock_db = client
        # User key lookup: return a real user row so get_current_user returns a user dict
        mock_db.execute.return_value = mock_result(rows=[(1, None)])
        with _mock_user_key_auth():
            resp = c.post(
                "/api/invites/",
                json={"max_uses": 1},
                headers=USER_API_KEY_HEADERS,
            )
        assert resp.status_code == 403
        assert "Settings key required" in resp.json()["detail"]

    def test_create_calls_db_with_correct_sql(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[INVITE_ROW])
        c.post("/api/invites/", json={"code": "abc123"}, headers=AUTH_HEADERS)
        call_args = mock_db.execute.call_args[0][0]
        assert isinstance(call_args, libsql_client.Statement)
        assert "INSERT INTO invites" in call_args.sql


class TestListInvites:
    def test_list_empty(self, client):
        c, _ = client
        resp = c.get("/api/invites/", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_multiple(self, client):
        c, mock_db = client
        row2 = (2, "xyz789", 10, 3, "2024-01-02")
        mock_db.execute.return_value = mock_result(rows=[row2, INVITE_ROW])
        resp = c.get("/api/invites/", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == 2
        assert data[0]["uses"] == 3

    def test_list_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.get("/api/invites/")
        assert resp.status_code == 401


class TestDeleteInvite:
    def test_delete_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        resp = c.delete("/api/invites/1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["message"] == "deleted"

    def test_delete_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.delete("/api/invites/999", headers=AUTH_HEADERS)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Invite not found"

    def test_delete_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.delete("/api/invites/1")
        assert resp.status_code == 401
