# Demo script (3–5 minutes)

## Before recording

1. Check Gemini quota in AI Studio, since a rate-limited Flash makes every answer use a fallback.
2. Start everything:
   - `ollama serve`
   - in `backend/`: `uv run uvicorn app.main:app --port 8000`
   - in `frontend/`: `npm run dev`
3. Open `http://localhost:5173` in a clean window, and `http://localhost:8000/docs` in a second tab.

## Script

| Time | Show | Say |
|---|---|---|
| 0:00 | README architecture diagram | The problem; RAG with a 3-layer grounding design; the stack in one line each |
| 0:30 | Swagger `/docs`: run `GET /health`, then `GET /passages?topic=soul` | The backend is independent of the UI; passages carry Sanskrit, Hindi and English, each credited to its edition and page |
| 1:00 | UI: click **"What does Garuda Purana explain about karma?"** | Loading stages; the answer is labelled **AI interpretation**; click a citation chip, which opens the source card with the verbatim text |
| 1:50 | Click the **Hindi soul's-journey** sample | Hindi question gets a Hindi answer; retrieval finds the passages across languages |
| 2:30 | Type **"Who won the 2011 Cricket World Cup?"** | Declined before any LLM call (fast); no invented answer |
| 2:50 | Type **"How can one cross it?"** after a Vaitaraṇī question | Follow-up context: retrieval also uses the previous question |
| 3:15 | Terminal: stop the backend, set `GEMINI_API_KEY=invalid` and restart (or show a response with a fallback notice) | Fallback chain: Gemini Flash → Flash-Lite → local Ollama; the UI shows which model answered |
| 3:45 | `docs/EVAL_RETRIEVAL.md` table and `uv run pytest` (85 passed) | BM25 vs semantic vs hybrid on real numbers; why hybrid; tests need no network |
| 4:15 | `docs/SCALABILITY.md` headings | Where it breaks first (LLM capacity), then cache, async calls, PostgreSQL + pgvector, Redis; mobile apps reuse the same API |

Keep the API key out of the recording: don't open `backend/.env` on screen.
