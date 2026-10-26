import { useEffect, useState } from 'react'
import { useT } from '../i18n'
import type { CommentaryLine, ViewerQuestion } from '../match/types'

const SHOW_AFTER_ANSWER_MS = 14000 // the answer stays up this long (or while it's being spoken)

/** The viewer's latest question, on the pitch: "Roy is looking at the data" while the match goes on,
 * then his answer, while it's spoken and a little after. The question is the show here: it's what
 * makes this broadcast yours. */
export function AnswerCard({ questions, lines, speakingId }: {
  questions: ViewerQuestion[]
  lines: CommentaryLine[]
  speakingId: string | null
}) {
  const t = useT()
  const question = questions[questions.length - 1]
  const answer = question ? lines.find((line) => line.reply_to === question.id) : undefined
  const [closed, setClosed] = useState<string | null>(null)
  const [expired, setExpired] = useState<string | null>(null) // the answer whose time on screen is up
  const answerId = answer?.id

  useEffect(() => {
    if (!answerId) return
    const timer = setTimeout(() => setExpired(answerId), SHOW_AFTER_ANSWER_MS)
    return () => clearTimeout(timer)
  }, [answerId])

  if (!question || closed === question.id) return null
  const speaking = !!answer && speakingId === answer.id
  if (answer && !speaking && expired === answer.id) return null

  return (
    <div className={`answer-card${answer ? ' answered' : ' thinking-card'}`} role="status" aria-live="polite">
      <div className="answer-q">
        <span className="answer-you">{t('You')} · {question.clock}</span>
        <p>“{question.text}”</p>
        <button type="button" className="answer-close" onClick={() => setClosed(question.id)}
          aria-label={t('Close')}>×</button>
      </div>
      {answer ? (
        <div className="answer-a" data-speaking={speaking}>
          <span className="answer-who">{t.voice('Roy')} · {t('Answering you')}</span>
          <p>{answer.text}</p>
          {/* the chart goes in the commentary feed, so the pitch stays visible */}
          {answer.chart && <span className="answer-chart-hint">{t('Chart in the commentary')} →</span>}
        </div>
      ) : (
        <div className="answer-wait">
          <span className="answer-dots" aria-hidden="true"><i /><i /><i /></span>
          {t('{name} is looking at the data… the match goes on', { name: t.voice('Roy') })}
        </div>
      )}
    </div>
  )
}
