import { type FormEvent, useRef, useState } from 'react'
import { MicIcon } from './Icons'

const SUGGESTIONS = ['What did I miss?', 'Why was that a foul?', 'Who has been better?']
const FULL_TIME_SUGGESTIONS = ['Who was the better team?', 'What was the key moment?', 'Was the result deserved?']

type MicState = 'idle' | 'listening' | 'error'

/**
 * Ask the analyst a question mid-match (#18), by typing or with the microphone (#21).
 * The mic is a toggle: press to talk, press again to stop and send. Typing always works,
 * even while listening, so the viewer can never be locked out of asking.
 * The match keeps going; Roy answers in a few seconds.
 */
export function QuestionBox({ open, fullTime, waiting, onAsk, onListening }: {
  open: boolean // during the match and after full time
  fullTime: boolean
  waiting: boolean
  onAsk: (q: string) => void
  onListening: (on: boolean) => void // the commentators go quiet while the viewer speaks
}) {
  const [text, setText] = useState('')
  const [mic, setMic] = useState<MicState>('idle')
  const [micError, setMicError] = useState('')
  const stopListening = useRef<AbortController | null>(null)

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!text.trim()) return
    stopListening.current?.abort() // typed while listening: stop the mic, the typed text wins
    onAsk(text.trim())
    setText('')
  }

  const toggleMic = async () => {
    if (mic === 'listening') {
      stopListening.current?.abort() // second press: stop and send what was heard
      return
    }
    const controller = new AbortController()
    stopListening.current = controller
    setMic('listening')
    setMicError('')
    setText('')
    onListening(true)
    try {
      // The Speech SDK is large: load it only when someone actually presses the mic.
      const { listenOnce } = await import('../audio/speechInput')
      const heard = await listenOnce(setText, controller.signal) // words appear as you speak
      if (heard.trim()) onAsk(heard.trim())
      else if (!controller.signal.aborted) setMicError("Didn't catch that. Try again?")
      setText('')
      setMic('idle')
    } catch (error) {
      setMic('error')
      setMicError(error instanceof Error && /permission|denied|NotAllowed/i.test(error.message)
        ? 'Microphone blocked. Allow it in the browser to ask by voice.'
        : error instanceof Error ? error.message : 'The microphone did not work.')
    } finally {
      stopListening.current = null
      onListening(false)
    }
  }

  const listening = mic === 'listening'
  return (
    <form className="ask" onSubmit={submit} aria-label="Ask the analyst">
      <div className="ask-row">
        <button type="button" className={`mic ${listening ? 'on' : ''}`} onClick={toggleMic} disabled={!open}
          aria-pressed={listening} aria-label={listening ? 'Stop and send' : 'Ask by voice'}
          title={listening ? 'Stop and send' : 'Ask by voice'}>
          {listening ? <span className="mic-dot" /> : <MicIcon />}
        </button>
        <input value={text} onChange={(e) => setText(e.target.value)} maxLength={200} disabled={!open}
          placeholder={listening ? 'Listening… press the mic again to send'
            : fullTime ? 'Full time: ask Roy about the match…'
            : open ? 'Ask Roy about the match…' : 'Kick off to ask questions'}
          aria-label="Your question" />
        <button type="submit" disabled={!open || !text.trim()}>Ask</button>
      </div>
      {open && (
        <div className="ask-hints">
          {micError ? (
            <span className="mic-error" role="status">{micError}</span>
          ) : listening ? (
            <span className="thinking">Listening… press the mic again when you're done</span>
          ) : waiting ? (
            <span className="thinking">Roy is thinking… the match goes on</span>
          ) : (
            (fullTime ? FULL_TIME_SUGGESTIONS : SUGGESTIONS).map((s) => (
              <button key={s} type="button" className="chip" onClick={() => onAsk(s)}>{s}</button>
            ))
          )}
        </div>
      )}
    </form>
  )
}
