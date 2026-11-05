# Scalability plan

The prototype is one FastAPI process with SQLite, an in-memory search index and an
in-memory rate limiter. Below is how it would grow, tied to where it would actually break.

## Where the time goes today (one request)

| Step | Typical cost | Scales with |
|---|---|---|
| Embed the question (e5-small, CPU) | ~20–50 ms | Number of requests (CPU) |
| BM25 + cosine over 18 passages | < 1 ms | Knowledge-base size |
| LLM call (Gemini Flash, minimal thinking) | ~4–12 s | Number of requests (API quota and cost) |
| SQLite reads and writes | < 5 ms | Writes (SQLite allows only one writer at a time) |

The LLM dominates by about 100× over everything else. So scaling is mostly about LLM
capacity, caching and concurrency, not the database.

## 1,000 users

Assume a few hundred questions a day, with occasional bursts.

- **Change:**
  - Run several Uvicorn workers behind a reverse proxy (nginx or Caddy).
  - Move to a paid Gemini tier; the free tier's per-minute limits would be hit.
  - Switch SQLite to WAL mode, or move to PostgreSQL to share the database between workers.
- **Keep:** the in-memory search index (each worker loads the 18 vectors at startup), and
  the passage JSON → ingest workflow.
- **Add:** basic monitoring (request rate, latency, LLM errors, how often fallbacks happen).

## 10,000 users

Assume thousands of questions a day and real concurrency.

- **Database:** PostgreSQL for passages, conversations and messages, with connection pooling.
- **Shared state:**
  - Move the rate limiter to **Redis**, so all instances share the counts.
  - Add a **Redis answer cache** keyed on (normalized question, retrieved passage IDs).
    Popular questions such as the sample ones would then cost no LLM call.
- **Concurrency:** make the LLM calls `async` (FastAPI and the Gemini SDK both support it),
  so a worker isn't held for 6 s per request.
- **Deployment:**
  - Put the API in a container and run 2+ instances behind a load balancer. The API holds
    no session state; conversation history lives in the database.
  - Serve the frontend as static files from a CDN.
- **LLM fallback:** replace the laptop Ollama step with a hosted open-model endpoint or a
  second paid provider.

## 100,000 users

- **Autoscaling:** autoscale the API containers (e.g. Kubernetes HPA, or Cloud Run) on
  CPU and number of requests in progress.
- **Queueing and streaming:**
  - Put LLM work behind a queue or worker pool with back-pressure.
  - Stream tokens to the client (server-sent events), so users see progress during long
    answers.
- **Separate embedding service:** run question embedding as its own service, with a GPU or
  batching, or use a hosted embedding API.
- **Users:** add authentication, per-user rate limits and quotas, and abuse detection.
- **Monitoring:** tracing across retrieval → LLM → validation; dashboards for groundedness
  (how often citations are rejected, how often questions are declined) as well as latency.
- **Cost control:** caching, cheaper models for simple questions, and token budgets per request.

## Many users at the same time

- **Already safe today:**
  - Endpoints are synchronous functions, so FastAPI runs them in a thread pool.
  - Each request opens its own SQLite connection.
  - The rate limiter uses a lock.
- **The limit:** about 40 requests can be in progress per process, each mostly waiting on
  the LLM. Moving to async LLM calls lets one process wait on hundreds of LLM requests.
- **SQLite:** writes are short (two message inserts per request), but at high write rates
  SQLite's single-writer lock becomes the bottleneck. That is the trigger for PostgreSQL.

## Larger knowledge base

| Size | Change |
|---|---|
| Hundreds of passages | No change: brute-force cosine over a NumPy matrix still takes milliseconds |
| Thousands to the full Purāṇa (~19,000 verses) | **pgvector** (HNSW index, a fast approximate nearest-neighbour search) inside PostgreSQL, so vectors and metadata live together; BM25 via PostgreSQL full-text search or OpenSearch |
| Many texts | Metadata filters (text, khanda, chapter), a cross-encoder **reranker** on the top 20, and chunking of long passages with links back to the parent verse |

The ingestion workflow stays the same: a reviewed source file, then validation, then
ingestion. Only the storage changes.

## Future Android and iOS apps

- **Reuse the API.** The REST API is already independent of any client: JSON in, JSON out,
  with consistent error responses. Version it (`/v1/ask`) before releasing mobile apps.
- **Clients:**
  - **React Native** reuses most of the current JavaScript (`api.js`, `useChat`).
  - **Flutter** is the alternative if a single codebase with native-looking UI matters more.
- **Mobile-specific needs:**
  - Token-based authentication.
  - Store conversation IDs on the device.
  - Offline access to the passage list. `GET /passages` is small and can be cached in full.
  - Push notifications are not needed.
- **Keys stay on the server.** The mobile apps, like the web app, never hold an LLM key;
  they only call the API.
