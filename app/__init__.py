import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

load_dotenv()

# Suppress aiohttp's noisy "Unclosed client session" warnings on shutdown
logging.getLogger("aiohttp.client").setLevel(logging.CRITICAL)
from fastapi.middleware.cors import CORSMiddleware

from app.database import close_client, init_db
from app.routers import todos, rag, settings, expenses

_db_initialized = False


class InitDbMiddleware(BaseHTTPMiddleware):
    """Run init_db on the first request — needed for Vercel serverless
    where FastAPI lifespan events don't fire."""

    async def dispatch(self, request: Request, call_next):
        global _db_initialized
        if not _db_initialized:
            await init_db()
            _db_initialized = True
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    global _db_initialized
    _db_initialized = True
    yield
    await close_client()


app = FastAPI(title="My Profile Backend", lifespan=lifespan)

app.add_middleware(InitDbMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(todos.router, prefix="/api/todos", tags=["todos"])
app.include_router(rag.router, prefix="/api/rag", tags=["rag"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(expenses.router, prefix="/api/expenses", tags=["expenses"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
