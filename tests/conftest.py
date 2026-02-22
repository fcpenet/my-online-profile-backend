import os
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Set env vars before importing the app
os.environ.setdefault("TURSO_DATABASE_URL", "https://fake-db.turso.io")
os.environ.setdefault("TURSO_AUTH_TOKEN", "fake-token")
os.environ.setdefault("OPENAI_API_KEY", "sk-fake-key")

TEST_API_KEY = "test-secret-key"
AUTH_HEADERS = {"X-API-Key": TEST_API_KEY}


def mock_result(rows=None):
    """Create a mock libsql_client result set."""
    result = MagicMock()
    result.rows = rows or []
    return result


async def _mock_get_api_key():
    return TEST_API_KEY


@pytest.fixture
def client():
    """Create a TestClient with all database calls and auth mocked."""
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result()
    mock_db.batch.return_value = []

    with patch("app.routers.todos.get_client", return_value=mock_db), \
         patch("app.routers.rag.get_client", return_value=mock_db), \
         patch("app.routers.settings.get_client", return_value=mock_db), \
         patch("app.routers.expenses.get_client", return_value=mock_db), \
         patch("app.routers.trips.get_client", return_value=mock_db), \
         patch("app.routers.projects.get_client", return_value=mock_db), \
         patch("app.routers.users.get_client", return_value=mock_db), \
         patch("app.routers.organizations.get_client", return_value=mock_db), \
         patch("app.routers.invites.get_client", return_value=mock_db), \
         patch("app.auth.get_client", return_value=mock_db), \
         patch("app.auth.get_api_key", side_effect=_mock_get_api_key), \
         patch("app.init_db", new_callable=AsyncMock):
        from app import app
        with TestClient(app) as c:
            yield c, mock_db
