"""Tests for settings endpoints (app/routers/settings.py)."""

from tests.conftest import AUTH_HEADERS, mock_result


class TestValidateKey:
    def test_validate_valid_key(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(
            rows=[("2099-01-01 00:00:00",)]
        )
        resp = c.get("/api/settings/validate-key", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["expires_at"] == "2099-01-01 00:00:00"

    def test_validate_without_key_returns_401(self, client):
        c, _ = client
        resp = c.get("/api/settings/validate-key")
        assert resp.status_code == 401

    def test_validate_wrong_key_returns_403(self, client):
        c, _ = client
        resp = c.get(
            "/api/settings/validate-key",
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 403


class TestRotateKey:
    def test_rotate_success(self, client):
        c, mock_db = client
        resp = c.post(
            "/api/settings/rotate-key",
            json={"new_key": "my-new-secret-key-12345"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "API key rotated"
        # Should have called execute to update the key
        assert mock_db.execute.called

    def test_rotate_without_key_returns_401(self, client):
        c, _ = client
        resp = c.post(
            "/api/settings/rotate-key",
            json={"new_key": "new-key-value-here"},
        )
        assert resp.status_code == 401

    def test_rotate_wrong_key_returns_403(self, client):
        c, _ = client
        resp = c.post(
            "/api/settings/rotate-key",
            json={"new_key": "new-key-value-here"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 403

    def test_rotate_key_too_short_returns_400(self, client):
        c, _ = client
        resp = c.post(
            "/api/settings/rotate-key",
            json={"new_key": "short"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 400
        assert "at least 8" in resp.json()["detail"]

    def test_rotate_missing_body_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/settings/rotate-key", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 422
