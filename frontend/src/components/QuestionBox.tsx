import { type FormEvent, useState } from 'react'
import { MicIcon } from './Icons'

const SUGGESTIONS = ['Why was that a foul?', 'Who has been better?', 'What is offside?']

type MicState = 'idle' | 'listening' | 'error'

/**
 * Ask the analyst a question mid-match (#18), by typing or with the microphone (#21).
 * The match keeps going; Sonia answers in a few seconds.
 */
export function QuestionBox({ live, waiting, onAsk, onListening }: {
  live: boolean
  waiting: boolean
  onAsk: (q: string) => void
  onListening: (on: boolean) => void // the commentators go quiet while the viewer speaks
}) {
  const [text, setText] = useState('')
  const [mic, setMic] = useState<MicState>('idle')
  const [micError, setMicError] = useState('')

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!text.trim()) return
    onAsk(text.trim())
    setText('')
  }

  const speak = async () => {
    if (mic === 'listening') return
    setMic('listening')
    setMicError('')
    setText('')
    onListening(true)
    try {
      // The Speech SDK is large: load it only when someone actually presses the mic.
      const { listenOnce } = await import('../audio/speechInput')
      const heard = await listenOnce(setText) // words appear as you speak
      if (heard.trim()) onAsk(heard.trim())
      else setMicError("Didn't catch that. Try again?")
      setText('')
      setMic('idle')
    } catch (error) {
      setMic('error')
      setMicError(error instanceof Error && /permission|denied|NotAllowed/i.test(error.message)
        ? 'Microphone blocked. Allow it in the browser to ask by voice.'
        : error instanceof Error ? error.message : 'The microphone did not work.')
    } finally {
      onListening(false)
    }
  }

  const listening = mic === 'listening'
  return (
    <form className="ask" onSubmit={submit} aria-label="Ask the analyst">
      <div className="ask-row">
        <button type="button" className={`mic ${listening ? 'on' : ''}`} onClick={speak} disabled={!live || listening}
          aria-label={listening ? 'Listening' : 'Ask by voice'} title="Ask by voice">
          {listening ? <span className="mic-dot" /> : <MicIcon />}
        </button>
        <input value={text} onChange={(e) => setText(e.target.value)} maxLength={200} disabled={!live || listening}
          placeholder={listening ? 'Listening… ask your question' : live ? 'Ask Sonia about the match…' : 'Kick off to ask questions'}
          aria-label="Your question" />
        <button type="submit" disabled={!live || listening || !text.trim()}>Ask</button>
      </div>
      {live && (
        <div className="ask-hints">
          {micError ? (
            <span className="mic-error" role="status">{micError}</span>
          ) : waiting ? (
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
