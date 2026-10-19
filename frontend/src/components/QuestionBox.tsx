import { type FormEvent, useState } from 'react'

const SUGGESTIONS = ['Why was that a foul?', 'Who has been better?', 'What is offside?']

/** Ask the analyst a question mid-match (#18). The match keeps going; Sonia answers in a few seconds. */
export function QuestionBox({ live, waiting, onAsk }: { live: boolean; waiting: boolean; onAsk: (q: string) => void }) {
  const [text, setText] = useState('')

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!text.trim()) return
    onAsk(text.trim())
    setText('')
  }

  return (
    <form className="ask" onSubmit={submit} aria-label="Ask the analyst">
      <div className="ask-row">
        <input value={text} onChange={(e) => setText(e.target.value)} maxLength={200} disabled={!live}
          placeholder={live ? 'Ask Sonia about the match…' : 'Kick off to ask questions'} aria-label="Your question" />
        <button type="submit" disabled={!live || !text.trim()}>Ask</button>
      </div>
      {live && (
        <div className="ask-hints">
          {waiting ? (
            <span className="thinking">🧠 Sonia is thinking… the match goes on</span>
          ) : (
            SUGGESTIONS.map((s) => (
              <button key={s} type="button" className="chip" onClick={() => onAsk(s)}>{s}</button>
            ))
          )}
        </div>
      )}
    </form>
  )
}
