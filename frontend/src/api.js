// Thin client for the FastAPI backend. Only the public backend URL lives in the frontend —
// API keys stay on the server.
const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

// Worst case the backend tries Gemini Flash, then Flash-Lite (30 s each), then local Ollama (120 s).
const ASK_TIMEOUT_MS = 180_000

export class ApiError extends Error {
  constructor(message, { status = 0, code = 'network_error' } = {}) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function request(path, { method = 'GET', body, timeoutMs = 15_000, signal } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort('timeout'), timeoutMs)
  signal?.addEventListener('abort', () => controller.abort('cancelled'))
  try {
    const res = await fetch(`${API_URL}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })
    const data = await res.json().catch(() => null)
    if (!res.ok) {
      // Backend errors always look like {"error": code, "message": text}
      throw new ApiError(data?.message || `Request failed (${res.status})`, {
        status: res.status,
        code: data?.error || 'http_error',
      })
    }
    return data
  } catch (err) {
    if (err instanceof ApiError) throw err
    if (controller.signal.aborted && controller.signal.reason === 'timeout') {
      throw new ApiError('The server took too long to answer. Please try again.', { code: 'timeout' })
    }
    throw new ApiError('Cannot reach the backend. Is it running on ' + API_URL + '?')
  } finally {
    clearTimeout(timer)
  }
}

export const askQuestion = (question, conversationId, signal) =>
  request('/ask', {
    method: 'POST',
    body: { question, ...(conversationId ? { conversation_id: conversationId } : {}) },
    timeoutMs: ASK_TIMEOUT_MS,
    signal,
  })

export const getHealth = () => request('/health', { timeoutMs: 5_000 })
