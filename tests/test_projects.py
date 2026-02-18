"""Tests for Projects/Epics/Tasks endpoints (app/routers/projects.py)."""

import libsql_client

from tests.conftest import AUTH_HEADERS, mock_result

PROJECT_ROW = (1, "My Project", "A description", "active", "2024-01-01", "2024-01-01")
EPIC_ROW = (1, 1, "Epic One", "Epic desc", "active", "2024-01-01", "2024-01-01")
TASK_ROW = (1, 1, "Task One", "Task desc", "2024-12-31", "todo", "bug", "2024-01-01", "2024-01-01")


# ── Projects ─────────────────────────────────────────────────────────────


class TestCreateProject:
    def test_create_success(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[PROJECT_ROW])
        resp = c.post(
            "/api/projects/",
            json={"title": "My Project", "description": "A description"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "My Project"
        assert data["status"] == "active"

    def test_create_missing_title_returns_422(self, client):
        c, _ = client
        resp = c.post("/api/projects/", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_create_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.post("/api/projects/", json={"title": "Test"})
        assert resp.status_code == 401

    def test_create_calls_db_with_correct_sql(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[PROJECT_ROW])
        c.post("/api/projects/", json={"title": "Test"}, headers=AUTH_HEADERS)
        call_args = mock_db.execute.call_args[0][0]
        assert isinstance(call_args, libsql_client.Statement)
        assert "INSERT INTO projects" in call_args.sql


class TestListProjects:
    def test_list_empty(self, client):
        c, _ = client
        resp = c.get("/api/projects/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_multiple(self, client):
        c, mock_db = client
        row2 = (2, "Second", None, "archived", "2024-01-02", "2024-01-02")
        mock_db.execute.return_value = mock_result(rows=[row2, PROJECT_ROW])
        resp = c.get("/api/projects/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_no_auth_required(self, client):
        c, _ = client
        resp = c.get("/api/projects/")
        assert resp.status_code == 200


class TestGetProject:
    def test_get_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[PROJECT_ROW])
        resp = c.get("/api/projects/1")
        assert resp.status_code == 200
        assert resp.json()["id"] == 1

    def test_get_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.get("/api/projects/999")
        assert resp.status_code == 404


class TestUpdateProject:
    def test_update_title(self, client):
        c, mock_db = client
        updated = (1, "Updated", "A description", "active", "2024-01-01", "2024-01-02")
        mock_db.execute.return_value = mock_result(rows=[updated])
        resp = c.patch("/api/projects/1", json={"title": "Updated"}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated"

    def test_update_empty_body_returns_400(self, client):
        c, _ = client
        resp = c.patch("/api/projects/1", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 400

    def test_update_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.patch("/api/projects/999", json={"title": "x"}, headers=AUTH_HEADERS)
        assert resp.status_code == 404


class TestDeleteProject:
    def test_delete_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        resp = c.delete("/api/projects/1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["message"] == "deleted"

    def test_delete_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.delete("/api/projects/999", headers=AUTH_HEADERS)
        assert resp.status_code == 404

    def test_delete_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.delete("/api/projects/1")
        assert resp.status_code == 401


# ── Epics ────────────────────────────────────────────────────────────────


class TestCreateEpic:
    def test_create_success(self, client):
        c, mock_db = client
        # First call: _get_project_or_404, second call: INSERT
        mock_db.execute.side_effect = [
            mock_result(rows=[(1,)]),
            mock_result(rows=[EPIC_ROW]),
        ]
        resp = c.post(
            "/api/projects/1/epics",
            json={"title": "Epic One", "description": "Epic desc"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Epic One"
        assert data["project_id"] == 1

    def test_create_project_not_found(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.post(
            "/api/projects/999/epics",
            json={"title": "Epic"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 404

    def test_create_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.post("/api/projects/1/epics", json={"title": "Epic"})
        assert resp.status_code == 401


class TestListEpics:
    def test_list_empty(self, client):
        c, mock_db = client
        # First call: _get_project_or_404, second call: SELECT epics
        mock_db.execute.side_effect = [
            mock_result(rows=[(1,)]),
            mock_result(rows=[]),
        ]
        resp = c.get("/api/projects/1/epics")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_project_not_found(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.get("/api/projects/999/epics")
        assert resp.status_code == 404


class TestGetEpic:
    def test_get_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[EPIC_ROW])
        resp = c.get("/api/projects/1/epics/1")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Epic One"

    def test_get_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.get("/api/projects/1/epics/999")
        assert resp.status_code == 404


class TestUpdateEpic:
    def test_update_status(self, client):
        c, mock_db = client
        updated = (1, 1, "Epic One", "Epic desc", "done", "2024-01-01", "2024-01-02")
        mock_db.execute.return_value = mock_result(rows=[updated])
        resp = c.patch(
            "/api/projects/1/epics/1", json={"status": "done"}, headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "done"

    def test_update_empty_body_returns_400(self, client):
        c, _ = client
        resp = c.patch("/api/projects/1/epics/1", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 400

    def test_update_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.patch(
            "/api/projects/1/epics/999", json={"title": "x"}, headers=AUTH_HEADERS
        )
        assert resp.status_code == 404


class TestDeleteEpic:
    def test_delete_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        resp = c.delete("/api/projects/1/epics/1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["message"] == "deleted"

    def test_delete_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.delete("/api/projects/1/epics/999", headers=AUTH_HEADERS)
        assert resp.status_code == 404


# ── Tasks ────────────────────────────────────────────────────────────────


class TestCreateTask:
    def test_create_success(self, client):
        c, mock_db = client
        # First call: _get_epic_or_404, second call: INSERT
        mock_db.execute.side_effect = [
            mock_result(rows=[(1,)]),
            mock_result(rows=[TASK_ROW]),
        ]
        resp = c.post(
            "/api/projects/1/epics/1/tasks",
            json={"title": "Task One", "description": "Task desc", "deadline": "2024-12-31", "label": "bug"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Task One"
        assert data["status"] == "todo"
        assert data["label"] == "bug"
        assert data["epic_id"] == 1

    def test_create_epic_not_found(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.post(
            "/api/projects/1/epics/999/tasks",
            json={"title": "Task"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 404

    def test_create_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.post("/api/projects/1/epics/1/tasks", json={"title": "Task"})
        assert resp.status_code == 401


class TestListTasks:
    def test_list_empty(self, client):
        c, mock_db = client
        mock_db.execute.side_effect = [
            mock_result(rows=[(1,)]),
            mock_result(rows=[]),
        ]
        resp = c.get("/api/projects/1/epics/1/tasks")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_epic_not_found(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.get("/api/projects/1/epics/999/tasks")
        assert resp.status_code == 404


class TestGetTask:
    def test_get_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[TASK_ROW])
        resp = c.get("/api/projects/1/epics/1/tasks/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Task One"
        assert data["deadline"] == "2024-12-31"

    def test_get_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.get("/api/projects/1/epics/1/tasks/999")
        assert resp.status_code == 404


class TestUpdateTask:
    def test_update_status(self, client):
        c, mock_db = client
        updated = (1, 1, "Task One", "Task desc", "2024-12-31", "in_progress", "bug", "2024-01-01", "2024-01-02")
        mock_db.execute.return_value = mock_result(rows=[updated])
        resp = c.patch(
            "/api/projects/1/epics/1/tasks/1",
            json={"status": "in_progress"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    def test_update_empty_body_returns_400(self, client):
        c, _ = client
        resp = c.patch("/api/projects/1/epics/1/tasks/1", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 400

    def test_update_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.patch(
            "/api/projects/1/epics/1/tasks/999",
            json={"title": "x"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 404


class TestDeleteTask:
    def test_delete_existing(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[(1,)])
        resp = c.delete("/api/projects/1/epics/1/tasks/1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["message"] == "deleted"

    def test_delete_nonexistent_returns_404(self, client):
        c, mock_db = client
        mock_db.execute.return_value = mock_result(rows=[])
        resp = c.delete("/api/projects/1/epics/1/tasks/999", headers=AUTH_HEADERS)
        assert resp.status_code == 404

    def test_delete_without_auth_returns_401(self, client):
        c, _ = client
        resp = c.delete("/api/projects/1/epics/1/tasks/1")
        assert resp.status_code == 401
