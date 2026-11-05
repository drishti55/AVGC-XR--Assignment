import { useEffect, useState } from 'react'
import { getHealth } from './api'
import ChatWindow from './components/ChatWindow'
import InputBar from './components/InputBar'
import SampleQuestions from './components/SampleQuestions'
import { useChat } from './hooks/useChat'

function HealthDot() {
  const [health, setHealth] = useState(null)
  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: 'down' }))
  }, [])
  const color = { ok: 'bg-green-500', degraded: 'bg-amber-500', down: 'bg-red-500' }[health?.status] || 'bg-stone-300'
  const label = !health ? 'Checking backend…' : health.status === 'down' ? 'Backend offline' : `Backend ${health.status} · ${health.passages} passages`
  return (
    <span className="flex items-center gap-1.5 text-xs text-stone-500" title={label}>
      <span className={`h-2 w-2 rounded-full ${color}`} />
      <span className="hidden sm:inline">{label}</span>
    </span>
  )
}

export default function App() {
  const { messages, loading, send, retry, clear } = useChat()

  return (
    <div className="flex min-h-dvh flex-col bg-stone-50 text-stone-900">
      <header className="sticky top-0 z-10 border-b border-stone-200 bg-stone-50/90 backdrop-blur">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-3 px-4 py-3">
          <div>
            <h1 className="text-base font-semibold sm:text-lg">
              Garuda Purana Q&amp;A <span className="font-deva font-normal text-stone-500">· गरुड़ पुराण</span>
            </h1>
            <p className="text-xs text-stone-500">Grounded answers with Sanskrit, Hindi and English sources</p>
          </div>
          <div className="flex items-center gap-3">
            <HealthDot />
            {messages.length > 0 && (
              <button type="button" onClick={clear} className="rounded-md border border-stone-300 px-2.5 py-1 text-xs hover:bg-white">
                New chat
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-6">
        {messages.length === 0 && !loading ? (
          <SampleQuestions onPick={send} disabled={loading} />
        ) : (
          <ChatWindow messages={messages} loading={loading} onRetry={retry} />
        )}
      </main>

      <footer className="sticky bottom-0 border-t border-stone-200 bg-stone-50/95 backdrop-blur">
        <div className="mx-auto max-w-4xl px-4 py-3">
          <InputBar onSend={send} disabled={loading} />
          <p className="mt-2 text-center text-[0.7rem] text-stone-400">
            AI interpretations can be imperfect — always read the cited original passages.
          </p>
        </div>
      </footer>
    </div>
  )
}
