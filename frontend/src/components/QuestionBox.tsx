import { type FormEvent, useRef, useState } from 'react'
import { MicIcon } from './Icons'
import type { Level } from './LevelPicker'
import { useT } from '../i18n'

const LEVEL_SUGGESTIONS: Record<Level, string[]> = {
  beginner: [
    'Why was that a foul?',
    'Explain offside rule',
    'What did I miss?',
  ],
  fan: [
    'Who has been better so far?',
    'Was that a red card?',
    'How does this affect the table?',
  ],
  analyst: [
    'Analyze our pressing structure',
    'What is the xG difference?',
    'How are half-spaces exploited?',
  ],
}

const LEVEL_FULL_TIME_SUGGESTIONS: Record<Level, string[]> = {
  beginner: [
    'Who won and why?',
    'What was the key moment?',
    'Explain the final score',
  ],
  fan: [
    'Who was the better team?',
    'Was the result deserved?',
    'How does this affect our season form?',
  ],
  analyst: [
    'Detailed xG & shot quality breakdown',
    'Tactical shifts that decided the match',
    'Possession efficiency analysis',
  ],
}

type MicState = 'idle' | 'listening' | 'error'

/**
 * Ask the analyst a question mid-match (#18), by typing or with the microphone (#21).
 * Suggestions are adapted dynamically to the viewer's level (Beginner, Fan, Analyst).
 */
export function QuestionBox({
  open,
  fullTime,
  waiting,
  level = 'fan',
  onAsk,
  onListening,
}: {
  open: boolean
  fullTime: boolean
  waiting: boolean
  level?: Level
  onAsk: (q: string) => void
  onListening: (on: boolean) => void
}) {
  const t = useT()
  const [text, setText] = useState('')
  const [mic, setMic] = useState<MicState>('idle')
  const [micError, setMicError] = useState('')
  const stopListening = useRef<AbortController | null>(null)

  const suggestions = fullTime
    ? LEVEL_FULL_TIME_SUGGESTIONS[level] ?? LEVEL_FULL_TIME_SUGGESTIONS.fan
    : LEVEL_SUGGESTIONS[level] ?? LEVEL_SUGGESTIONS.fan

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!text.trim()) return
    stopListening.current?.abort()
    onAsk(text.trim())
    setText('')
  }

  const toggleMic = async () => {
    if (mic === 'listening') {
      stopListening.current?.abort()
      return
    }
    const controller = new AbortController()
    stopListening.current = controller
    setMic('listening')
    setMicError('')
    setText('')
    onListening(true)
    try {
      const { listenOnce } = await import('../audio/speechInput')
      const heard = await listenOnce(setText, controller.signal, t.lang === 'es' ? 'es-MX' : 'en-US')
      if (heard.trim()) onAsk(heard.trim())
      else if (!controller.signal.aborted) setMicError(t("Didn't catch that. Try again?"))
      setText('')
      setMic('idle')
    } catch (error) {
      setMic('error')
      setMicError(
        error instanceof Error && /permission|denied|NotAllowed/i.test(error.message)
          ? t('Microphone blocked. Allow it in the browser to ask by voice.')
          : error instanceof Error
            ? error.message
            : t('The microphone did not work.'),
      )
    } finally {
      stopListening.current = null
      onListening(false)
    }
  }

  const listening = mic === 'listening'
  return (
    <form className="ask dock" onSubmit={submit} aria-label={t('Ask the analyst')}>
      <div className="ask-head">
        <span className="ask-title">{t('Ask {name}', { name: t.voice('Roy') })}</span>
        <span className="ask-sub">{t('By voice or text. The match keeps playing while he answers.')}</span>
      </div>
      <div className="ask-row">
        <button
          type="button"
          className={`mic ${listening ? 'on' : ''}`}
          onClick={toggleMic}
          disabled={!open}
          aria-pressed={listening}
          aria-label={t(listening ? 'Stop and send' : 'Ask by voice')}
          title={t(listening ? 'Stop and send' : 'Ask by voice')}
        >
          {listening ? <span className="mic-dot" /> : <MicIcon size={26} />}
        </button>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={200}
          disabled={!open}
          placeholder={
            listening
              ? t('Listening… press the mic again to send')
              : fullTime
                ? t('Full time: ask Roy about the match…')
                : open
                  ? t('Ask Roy about the match…')
                  : t('Kick off to ask questions')
          }
          aria-label={t('Your question')}
        />
        <button type="submit" disabled={!open || !text.trim()}>
          {t('Ask')}
        </button>
      </div>
      {open && (
        <div className="ask-hints">
          {micError ? (
            <span className="mic-error" role="status">
              {micError}
            </span>
          ) : listening ? (
            <span className="thinking">{t("Listening… press the mic again when you're done")}</span>
          ) : waiting ? (
            <span className="thinking">{t('Roy is thinking… the match goes on')}</span>
          ) : (
            suggestions.map((s) => (
              <button
                key={s}
                type="button"
                className="chip ask-level-chip"
                data-level={level}
                onClick={() => onAsk(t(s))}
                title={`Ask: "${t(s)}"`}
              >
                {t(s)}
              </button>
            ))
          )}
        </div>
      )}
    </form>
  )
}
