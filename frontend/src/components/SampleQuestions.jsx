// The assignment's five sample questions, as one-click shortcuts.
const SAMPLES = [
  'What does Garuda Purana explain about karma?',
  'What does the text describe about the soul?',
  'What is the significance of good deeds?',
  'गरुड़ पुराण में कर्म के बारे में क्या बताया गया है?',
  'गरुड़ पुराण के अनुसार मृत्यु के बाद आत्मा की यात्रा का क्या वर्णन है?',
]

export default function SampleQuestions({ onPick, disabled }) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <h2 className="text-lg font-medium text-stone-800">Ask about the Garuda Purana</h2>
      <p className="mt-1 text-sm text-stone-500">
        Answers are generated only from 18 verified passages of the Garuda Purana Sāroddhāra, with the original
        Sanskrit, Hindi and English shown for every source.
      </p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        {SAMPLES.map((q) => (
          <button
            key={q}
            type="button"
            disabled={disabled}
            onClick={() => onPick(q)}
            className="rounded-full border border-stone-300 bg-white px-3 py-1.5 font-deva text-sm text-stone-700 hover:border-amber-500 hover:bg-amber-50 disabled:opacity-50"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}
