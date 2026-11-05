import { useState } from 'react'
import SourceCard from './SourceCard'

const CITATION = /\[(GPS-\d{2}-\d{3}(?:\s*[,;]\s*GPS-\d{2}-\d{3})*)\]/g

// Turn "[GPS-02-015, GPS-02-066]" markers into clickable chips. Plain text only —
// no HTML is ever injected from the response.
function AnswerText({ text, onCite }) {
  return text.split(/\n{2,}/).map((para, i) => {
    const parts = []
    let last = 0
    for (const m of para.matchAll(CITATION)) {
      parts.push(para.slice(last, m.index))
      for (const id of m[1].split(/\s*[,;]\s*/)) {
        parts.push(
          <button
            key={`${m.index}-${id}`}
            type="button"
            onClick={() => onCite(id)}
            className="mx-0.5 rounded bg-amber-100 px-1.5 py-0.5 align-baseline font-mono text-[0.7rem] text-amber-900 hover:bg-amber-200"
            title="Show this passage"
          >
            {id}
          </button>,
        )
      }
      last = m.index + m[0].length
    }
    parts.push(para.slice(last))
    return (
      <p key={i} className="mt-2 first:mt-0 leading-relaxed">
        {parts}
      </p>
    )
  })
}

const NOTICES = {
  llm_unavailable: 'The AI service is unavailable, so only the relevant passages are shown.',
}

function noticeText(notice) {
  if (!notice) return null
  if (notice.startsWith('fallback_used:')) {
    const [, provider, reason] = notice.split(':')
    return `Primary model (${provider}) was ${reason.replace('_', ' ')} — answered by a fallback model.`
  }
  return NOTICES[notice] || notice
}

function AssistantMessage({ response }) {
  const [highlight, setHighlight] = useState(null)
  const cite = (id) => {
    setHighlight(id)
    const el = document.getElementById(`src-${id}`)
    if (el) {
      el.open = true
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }
  const cards = response.sources.length ? response.sources : response.related_passages
  const notice = noticeText(response.notice)

  return (
    <div className="w-full max-w-3xl">
      <div
        lang={response.language}
        className={`rounded-xl border px-4 py-3 ${response.answerable ? 'border-amber-200 bg-amber-50' : 'border-stone-200 bg-stone-100'}`}
      >
        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
          <span className={`rounded-full px-2 py-0.5 font-medium ${response.answerable ? 'bg-amber-200 text-amber-900' : 'bg-stone-200 text-stone-700'}`}>
            {response.answer_label}
          </span>
        </div>
        <div className={`text-[0.95rem] text-stone-800 ${response.language === 'hi' ? 'font-deva' : ''}`}>
          <AnswerText text={response.answer} onCite={cite} />
        </div>
        <div className="mt-3 text-[0.7rem] text-stone-500">
          {response.model ? `Model: ${response.model} · ` : ''}
          {(response.latency_ms / 1000).toFixed(1)} s
          {response.sources.length > 0 && ` · ${response.sources.length} cited passage${response.sources.length > 1 ? 's' : ''}`}
        </div>
        {notice && <div className="mt-2 rounded bg-white/70 px-2 py-1 text-xs text-amber-800">⚠ {notice}</div>}
      </div>

      {cards.length > 0 && (
        <div className="mt-3">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-500">
            {response.sources.length ? 'Sources — original text and translations' : 'Relevant passages'}
          </h3>
          <div className="space-y-2">
            {cards.map((p, i) => (
              <SourceCard key={p.id} passage={p} defaultOpen={i === 0} highlighted={highlight === p.id} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function MessageBubble({ message, onRetry }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-stone-800 px-4 py-2 text-white font-deva sm:max-w-[70%]">
          {message.text}
        </div>
      </div>
    )
  }
  if (message.error) {
    return (
      <div className="max-w-3xl rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
        <p>{message.error}</p>
        <button
          type="button"
          onClick={() => onRetry(message.retryQuestion)}
          className="mt-2 rounded-md bg-red-600 px-3 py-1 text-xs font-medium text-white hover:bg-red-700"
        >
          Retry
        </button>
      </div>
    )
  }
  return <AssistantMessage response={message.response} />
}
