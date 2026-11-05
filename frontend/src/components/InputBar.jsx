import { useState } from 'react'

const MAX = 500 // must match the backend's limit

export default function InputBar({ onSend, disabled }) {
  const [text, setText] = useState('')
  const trimmed = text.trim()
  const canSend = !disabled && trimmed.length >= 2 && text.length <= MAX

  const submit = (e) => {
    e.preventDefault()
    if (!canSend) return
    onSend(trimmed)
    setText('')
  }

  return (
    <form onSubmit={submit} className="flex items-end gap-2">
      <div className="relative flex-1">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) submit(e) // Shift+Enter = new line
          }}
          rows={2}
          maxLength={MAX}
          placeholder="Ask in English or हिन्दी…"
          aria-label="Your question"
          className="block w-full resize-none rounded-xl border border-stone-300 bg-white px-4 py-3 pr-16 font-deva text-[0.95rem] shadow-sm outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
        />
        <span className={`pointer-events-none absolute bottom-2 right-3 text-[0.7rem] ${text.length > MAX - 50 ? 'text-red-600' : 'text-stone-400'}`}>
          {text.length}/{MAX}
        </span>
      </div>
      <button
        type="submit"
        disabled={!canSend}
        className="h-[3.25rem] shrink-0 rounded-xl bg-amber-600 px-5 font-medium text-white shadow-sm hover:bg-amber-700 disabled:cursor-not-allowed disabled:bg-stone-300"
      >
        {disabled ? '…' : 'Ask'}
      </button>
    </form>
  )
}
