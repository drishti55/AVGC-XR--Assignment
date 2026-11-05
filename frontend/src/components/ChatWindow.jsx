import { useEffect, useRef } from 'react'
import LoadingIndicator from './LoadingIndicator'
import MessageBubble from './MessageBubble'

export default function ChatWindow({ messages, loading, onRetry }) {
  const endRef = useRef(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, loading])

  return (
    <div className="space-y-6" aria-live="polite">
      {messages.map((m) => (
        <MessageBubble key={m.id} message={m} onRetry={onRetry} />
      ))}
      {loading && <LoadingIndicator />}
      <div ref={endRef} />
    </div>
  )
}
