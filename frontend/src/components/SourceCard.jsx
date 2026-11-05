// One knowledge-base passage, shown verbatim from the database. Each language layer is
// labelled with its own edition so original text, translations and the AI interpretation
// can never be confused.

function editionLabel(edition, withTranslator) {
  if (!edition) return ''
  const who = withTranslator && edition.translator ? `${edition.translator}, ` : ''
  return `${who}${edition.publisher}${edition.year ? `, ${edition.year}` : ''}`
}

// The original Sanskrit has an edition but no translator; translations credit both.
function Layer({ title, edition, page, lang, original = false, children }) {
  return (
    <section className="mt-3 first:mt-0">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-stone-500">
        {title}
        <span className="ml-1 font-normal normal-case tracking-normal text-stone-400">
          — {editionLabel(edition, !original)}
          {page ? `, p. ${page}` : ''}
        </span>
      </h4>
      <p lang={lang} className={`mt-1 whitespace-pre-line text-stone-800 ${lang !== 'en' ? 'font-deva leading-relaxed' : 'leading-relaxed'}`}>
        {children}
      </p>
    </section>
  )
}

export default function SourceCard({ passage, defaultOpen = false, highlighted = false }) {
  const verses = passage.verse_ref_en || passage.verse_ref_sa
  return (
    <details
      id={`src-${passage.id}`}
      open={defaultOpen}
      className={`group rounded-lg border bg-white transition-shadow ${highlighted ? 'border-amber-500 shadow-md' : 'border-stone-200'}`}
    >
      <summary className="flex cursor-pointer list-none items-start justify-between gap-3 px-4 py-3">
        <div>
          <div className="text-sm font-medium text-stone-900">
            Chapter {passage.chapter} · {passage.chapter_title}
          </div>
          <div className="mt-0.5 text-xs text-stone-500">
            Verses {verses} · {passage.khanda.split(' — ')[0]} · <span className="font-mono">{passage.id}</span>
          </div>
        </div>
        <span className="mt-0.5 text-stone-400 transition-transform group-open:rotate-90" aria-hidden>
          ›
        </span>
      </summary>

      <div className="border-t border-stone-100 px-4 py-3 text-sm">
        {passage.sanskrit && (
          <Layer title="Original Sanskrit" edition={passage.editions.sanskrit} page={passage.page_sa} lang="sa" original>
            {passage.sanskrit}
          </Layer>
        )}
        <Layer title="Hindi translation" edition={passage.editions.hindi} page={passage.page_sa} lang="hi">
          {passage.hindi}
        </Layer>
        <Layer title="English translation" edition={passage.editions.english} page={passage.page_en} lang="en">
          {passage.english}
        </Layer>
        {passage.notes && <p className="mt-3 text-xs italic text-stone-500">Note: {passage.notes}</p>}
      </div>
    </details>
  )
}
