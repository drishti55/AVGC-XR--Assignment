import { useCallback, useEffect, useRef, useState } from 'react'
import { askQuestion } from '../api'

const STORAGE_KEY = 'garuda-chat-v1'

// sessionStorage keeps the chat across page refreshes during this browser session.
// It can be unavailable (private mode, blocked storage), so every access is guarded.
function load() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY))
    if (saved && Array.isArray(saved.messages)) return saved
  } catch {
    /* ignore */
  }
  return { messages: [], conversationId: null }
}

function save(state) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    /* ignore */
  }
}

let nextId = Date.now()
const newId = () => String(nextId++)

export function useChat() {
  const [{ messages, conversationId }, setState] = useState(load)
  const [loading, setLoading] = useState(false)
  const inFlight = useRef(null)

  useEffect(() => save({ messages, conversationId }), [messages, conversationId])

  const send = useCallback(
    async (rawQuestion) => {
      const question = rawQuestion.trim()
      if (!question || loading) return
      const userMsg = { id: newId(), role: 'user', text: question }
      setState((s) => ({ ...s, messages: [...s.messages.filter((m) => !m.error), userMsg] }))
      setLoading(true)

      const controller = new AbortController()
      inFlight.current = controller
      try {
        const res = await askQuestion(question, conversationId, controller.signal)
        setState((s) => ({
          conversationId: res.conversation_id,
          messages: [...s.messages, { id: newId(), role: 'assistant', response: res }],
        }))
      } catch (err) {
        if (controller.signal.aborted && !err.code?.includes('timeout')) return
        setState((s) => ({
          ...s,
          messages: [...s.messages, { id: newId(), role: 'assistant', error: err.message, retryQuestion: question }],
        }))
      } finally {
        setLoading(false)
        inFlight.current = null
      }
    },
    [conversationId, loading],
  )

  const retry = useCallback(
    (question) => {
      // Drop the failed user message + error, then ask again.
      setState((s) => {
        const msgs = s.messages.filter((m) => !m.error)
        const last = msgs[msgs.length - 1]
        return { ...s, messages: last?.role === 'user' && last.text === question ? msgs.slice(0, -1) : msgs }
      })
      send(question)
    },
    [send],
  )

  const clear = useCallback(() => {
    inFlight.current?.abort()
    setLoading(false)
    setState({ messages: [], conversationId: null })
  }, [])

  return { messages, loading, send, retry, clear }
}
