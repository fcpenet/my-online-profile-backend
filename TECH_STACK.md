# Tech Stack Decision Record

This document records the technology choices made for this backend, the alternatives considered, and the reasoning behind each decision. The primary constraint driving all decisions is **deployment on Vercel's free tier** (serverless, no persistent filesystem, 60s max function timeout).

---

## Framework: Python + FastAPI

**Chosen:** FastAPI

**Why FastAPI:**
- **Native async/await** — critical for making concurrent calls to OpenAI and Turso without blocking
- **Automatic API documentation** — interactive Swagger UI at `/docs` out of the box
- **Pydantic integration** — request/response validation and serialization with zero boilerplate
- **Strong AI/ML ecosystem** — first-class Python means direct access to OpenAI SDK and embedding libraries
- **Lightweight** — minimal footprint, well-suited for serverless deployment

| Alternative | Why not chosen |
|---|---|
| Node.js + Express (TypeScript) | Python has a stronger ecosystem for RAG/AI use cases (OpenAI SDK, embedding libraries). FastAPI's async support and auto-generated docs (`/docs`) make it more productive for API development. |
| Python + Flask | Flask is synchronous by default. FastAPI provides native async support (important for concurrent OpenAI and database calls), automatic request validation via Pydantic, and built-in OpenAPI documentation. |

---

## Database: Turso (libSQL)

**Chosen:** Turso — a cloud-hosted SQLite-compatible database accessible over HTTPS.

**Why Turso:**
- **Serverless-compatible** — accessible over HTTPS, no local filesystem required
- **SQLite-compatible syntax** — familiar SQL with no learning curve
- **Generous free tier** — 9 GB storage, 500 databases, 25M monthly row reads
- **Low latency** — edge-replicated databases with global distribution
- **Zero operational overhead** — fully managed, no server to provision or maintain

| Alternative | Why not chosen |
|---|---|
| SQLite (local file) | Vercel serverless functions have **no persistent filesystem**. A local SQLite file would be lost between invocations, making it unusable for production. |
| PostgreSQL | Requires a running Postgres instance. More operational overhead for a simple project. Turso's free tier is sufficient and simpler to set up. |
| In-memory only | Data resets on every cold start in a serverless environment — effectively no persistence at all. |

**Client library:** `libsql-client` (not `libsql`)

| Alternative | Why not chosen |
|---|---|
| `libsql` (newer Rust-based SDK) | Requires a local `.db` file as a sync target for its embedded replica pattern. This won't work on Vercel where there is no persistent filesystem. |

`libsql-client` is a pure Python HTTP client that connects to Turso over HTTPS with no local file or native binary dependencies — ideal for serverless.

---

## Vector Store: Turso (embeddings stored as JSON)

**Chosen:** Store embedding vectors as JSON text in a Turso column, compute cosine similarity in pure Python.

**Why JSON-in-Turso:**
- **No extra service** — reuses the same Turso database already needed for todos, reducing infrastructure complexity
- **Simple implementation** — standard JSON serialization, no special SDK or binary dependencies
- **Adequate performance** — cosine similarity over <100 vectors of 1536 dimensions takes ~10-20ms in pure Python
- **Small bundle size** — avoids pulling in numpy, FAISS, or chromadb, staying well under Vercel's 250MB limit
- **Full control** — no vendor lock-in to a specific vector database provider

| Alternative | Why not chosen |
|---|---|
| FAISS (in-memory) | FAISS indexes cannot persist on Vercel serverless — they would need to be rebuilt on every cold start. For a single-document use case this adds latency with no benefit. |
| ChromaDB Cloud | Adds a third external service to manage (on top of Turso and OpenAI). For single-document scale (<100 vectors), a dedicated vector database is unnecessary overhead. |
| Pinecone | Managed cloud vector DB requiring an API key and account. Same reasoning as ChromaDB — overkill for single-document scale. |

For a single document chunked into ~50 pieces, computing cosine similarity over 1536-dimensional vectors in pure Python takes roughly 10-20ms. No numpy or native dependencies are needed, which also keeps the Vercel function bundle small.

---

## LLM Provider: OpenAI

**Chosen:** OpenAI — `text-embedding-3-small` for embeddings, `gpt-4o-mini` for generation.

**Why OpenAI:**
- **Single provider** — handles both embeddings and generation, no need to integrate multiple APIs
- **Fast response times** — typically 1-3s per call, well within Vercel's timeout limits
- **High reliability** — production-grade SLA with consistent uptime
- **Cost-effective at scale** — embeddings at $0.02/1M tokens, generation at $0.15/1M input tokens (~pennies/month for this project)
- **Quality** — `gpt-4o-mini` excels at grounded Q&A tasks; `text-embedding-3-small` produces high-quality 1536-dim vectors

| Alternative | Why not chosen |
|---|---|
| HuggingFace Inference API (free tier) | **Cold starts of 20-60s** when models are idle. Combined with Vercel's function timeout, this would cause frequent request failures. No reliability SLA. Open-source model quality is generally lower for grounded Q&A. |
| Google Gemini (free tier) | Viable option with 15 requests/minute on the free tier. OpenAI was preferred for its simpler single-provider setup (both embeddings and generation) and broader ecosystem support. |
| Ollama (local) | Requires a running local server — cannot run on Vercel serverless. Only suitable for local development. |
| Anthropic (Claude) | Does not offer an embedding model, so a second provider would still be needed for embeddings. Adds integration complexity for no clear benefit in this use case. |

OpenAI costs for this project are minimal (~pennies/month): `text-embedding-3-small` at $0.02/1M tokens and `gpt-4o-mini` at $0.15/1M input tokens.

---

## Deployment: Vercel Free Tier

**Chosen:** Vercel serverless Python runtime.

**Why Vercel:**
- **Zero ops** — no servers to manage, automatic scaling, built-in CI/CD from git push
- **Free tier** — sufficient for a personal project (100 GB bandwidth, 60s function timeout)
- **Python support** — native FastAPI integration with automatic ASGI detection
- **Global edge network** — fast response times worldwide
- **Simple environment variables** — secrets managed through the dashboard, no extra config

Key constraints that shaped other decisions:
- **No persistent filesystem** → ruled out SQLite, FAISS, Ollama
- **60s max function timeout (hobby plan)** → ruled out slow providers like HuggingFace free tier
- **250MB bundle limit** → favored lightweight dependencies (no numpy, torch, or chromadb)
- **Stateless cold starts** → database tables are created with `IF NOT EXISTS` on each lifespan init

---

## Package Manager: uv

**Chosen:** `uv` — fast Python package manager and project tool.

**Why uv:**
- **Speed** — 10-100x faster than pip for dependency resolution and installation
- **Lockfile** — `uv.lock` ensures reproducible builds across environments
- **All-in-one** — replaces pip, venv, pip-tools, and pyenv in a single tool
- **Modern standards** — uses `pyproject.toml` natively, no extra config files needed

| Alternative | Why not chosen |
|---|---|
| pip + venv | Slower dependency resolution and installation. No lockfile by default. `uv` provides a `uv.lock` lockfile for reproducible builds and is significantly faster. |
| poetry | Heavier tool with more configuration overhead. `uv` is simpler and faster for this project's needs. |

---

## Summary

| Component | Choice | Key reason |
|---|---|---|
| Framework | FastAPI | Async, auto-docs, Pydantic validation, strong AI ecosystem |
| Database | Turso (libSQL) | Cloud SQLite over HTTPS, works on serverless, free tier |
| Vector store | JSON in Turso | Single-document scale, no extra service needed |
| Embeddings | OpenAI `text-embedding-3-small` | Cheap, fast, reliable |
| Generation | OpenAI `gpt-4o-mini` | Cheap, fast, good at grounded Q&A |
| Turso client | `libsql-client` | Pure Python HTTP, no filesystem needed |
| Deployment | Vercel free tier | Serverless Python, zero ops |
| Package manager | uv | Fast, lockfile support, modern |
