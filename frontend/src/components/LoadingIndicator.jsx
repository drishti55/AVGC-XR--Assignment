import { useEffect, useState } from 'react'

// Shows what the backend is doing; the longer wait message appears if a fallback model is in use.
export default function LoadingIndicator() {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [])

  const stage =
    seconds < 2 ? 'Searching the passages…' : seconds < 20 ? 'Generating an answer from the passages…' : 'Still working — the primary model may be busy, trying a fallback…'

  return (
    <div role="status" aria-live="polite" className="flex items-center gap-3 text-sm text-stone-500">
      <span className="flex gap-1" aria-hidden>
        {[0, 150, 300].map((d) => (
          <span key={d} className="h-2 w-2 animate-bounce rounded-full bg-amber-500" style={{ animationDelay: `${d}ms` }} />
        ))}
      </span>
      <span>
        {stage} <span className="tabular-nums text-stone-400">{seconds}s</span>
      </span>
    </div>
  )
}
