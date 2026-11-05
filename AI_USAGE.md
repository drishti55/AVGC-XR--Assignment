# AI tools, libraries and third-party material

The assignment allows AI coding assistants and asks for them to be disclosed. This file
lists everything used.

## AI coding assistant

**Claude Code (Anthropic, Claude Opus 5.5)** was used throughout, as an assistant for
architecture planning, writing code, tests and documentation, and checking the
knowledge-base text.

How it was used:

- **Technology choices:** the assistant compared options for each part of the stack. I chose
  the final stack, including the local Ollama fallback, JavaScript rather than TypeScript,
  local-only deployment and hybrid search.
- **Knowledge base:**
  - The assistant found the editions and extracted the text from the archive.org OCR and
    the sacred-texts transcription.
  - It proofread every passage against the scanned page images and fixed OCR errors, so the
    text matches the printed page.
  - No scripture text was typed from memory or generated. The method is documented in
    [docs/SOURCES.md](docs/SOURCES.md).
- **Code:** written with the assistant, milestone by milestone. Each milestone was tested
  (automated tests, plus live runs against the API and the UI) and approved by me before
  it was committed.
- **Evaluation:** the questions in `backend/tests/eval_questions.json` were written during
  development. The relevance-gate thresholds were set on them (see the caveats in
  [docs/EVAL_RETRIEVAL.md](docs/EVAL_RETRIEVAL.md)).
- **Demo video:** [docs/demo/demo.mp4](docs/demo/demo.mp4) is a real screen recording of
  the running app (backend, frontend and live Gemini calls). The assistant drove the browser
  with Playwright and added on-screen captions instead of narration. Nothing in it is mocked
  or edited; one answer shows the real fallback notice from a moment when Gemini Flash was
  overloaded.

## AI models used by the application

| Model | Used for | Access |
|---|---|---|
| Google Gemini 3.5 Flash / Flash-Lite | Generating answers (1st and 2nd attempt) | Gemini API, free tier |
| Qwen 2.5 7B Instruct (Alibaba, Apache-2.0) | Generating answers (local fallback) | Ollama |
| intfloat/multilingual-e5-small (MIT) | Question and passage embeddings | Hugging Face, runs locally |

## Libraries

- **Backend:**
  - FastAPI, Uvicorn, Pydantic and pydantic-settings
  - sentence-transformers (with PyTorch and transformers) and NumPy
  - rank-bm25
  - google-genai and httpx
  - pytest
- **Frontend:** React, Vite, Tailwind CSS, oxlint.
- **Development only, not in the repository:**
  - PyMuPDF, to render scan pages for proofreading.
  - Playwright, to drive the UI in a headless browser for testing and to record the demo video.
  - ffmpeg (via imageio-ffmpeg), to convert the recording to MP4.

## Source texts

| Material | Use | Status |
|---|---|---|
| Ernest Wood & S. V. Subrahmanyam, *The Garuḍa Purāṇa (Sāroddhāra)*, 1911 | English translations | Public domain |
| Gita Press, Gorakhpur, *गरुडपुराण-सारोद्धार (सानुवाद)*, book code 1416 | Sanskrit text and Hindi translations | © Gita Press. 18 short excerpts quoted with attribution for non-commercial educational use |
