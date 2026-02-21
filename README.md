# My Online Profile Backend

Python FastAPI backend deployed on Vercel. Provides a to-do list API, RAG (retrieval-augmented generation) endpoint, expense tracking, project management, and user/organization management.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

## Setup

```bash
uv sync
```

Copy `.env.example` to `.env` and fill in your credentials:

```
TURSO_DATABASE_URL=libsql://your-db.turso.io
TURSO_AUTH_TOKEN=your-token
OPENAI_API_KEY=sk-...
```

## Running locally

```bash
uv run uvicorn app:app --reload
```

Server starts at `http://localhost:8000`. The `--reload` flag restarts automatically on file changes.

> If port 8000 is stuck after a crash: `lsof -i :8000` then `kill <PID>`

## Running tests

```bash
.venv/bin/pytest tests/ -v
```

All tests use mocked database and auth — no live Turso connection required.

## API overview

| Prefix | Description | Auth |
|---|---|---|
| `GET /api/todos/` | To-do list (read) | Public |
| `POST/PATCH/DELETE /api/todos/` | To-do list (write) | Required |
| `GET /api/rag/documents` | List documents | Public |
| `POST /api/rag/ingest` | Ingest document | Required |
| `POST /api/rag/query` | Query documents | Public |
| `/api/expenses/` | Expense tracking | Required |
| `/api/organizations/` | Organization management | Required |
| `/api/projects/` | Projects, epics, tasks | Required |
| `POST /api/users/register` | Register user | Public |
| `POST /api/users/login` | Login (returns API key) | Public |
| `GET /api/settings/validate-key` | Check key validity | Required |
| `POST /api/settings/rotate-key` | Rotate API key | Required |

### Authentication

Pass your API key in the `X-API-Key` header:

```
X-API-Key: your-api-key
```

There are two key types:

- **Settings key** — auto-generated on startup, stored in Turso. Acts as a superuser (bypasses org checks). Retrieve from the Turso console.
- **User key** — returned by `POST /api/users/login`. Scoped to the user's organization.
