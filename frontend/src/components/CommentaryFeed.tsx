import { useState } from 'react'
import type { CommentaryLine, ViewerQuestion } from '../match/types'
import { useT } from '../i18n'

const VOICES = {
  caller: { name: 'Davis', role: 'Play-by-play' },
  analyst: { name: 'Roy', role: 'Analyst' },
} as const

/**
 * The commentary as a live feed: newest on top, the line being spoken highlighted.
 * Viewer questions show as "You" bubbles until Roy answers; his answer quotes the question.
 * Also provides a toggle to view only Questions & Answers right in the sidebar.
 */
export function CommentaryFeed({ lines, questions, speakingId }: {
  lines: CommentaryLine[]
  questions: ViewerQuestion[]
  speakingId: string | null
}) {
  const t = useT()
  const [tab, setTab] = useState<'feed' | 'qa'>('feed')

  const answered = new Set(lines.map((line) => line.reply_to).filter(Boolean))
  const pending = questions.filter((q) => !answered.has(q.id)).reverse()
  const byId = new Map(questions.map((q) => [q.id, q]))

  // All Q&A pairs (questions + answers from Roy)
  const answersByQuestionId = new Map<string, CommentaryLine>()
  for (const line of lines) {
    if (line.reply_to) {
      answersByQuestionId.set(line.reply_to, line)
    }
  }

  const qaList = [...questions].reverse().map((q) => ({
    question: q,
    answer: answersByQuestionId.get(q.id),
  }))

  return (
    <section className="card feed" aria-label={t('Commentary')} aria-live="polite">
      <div className="feed-header-row">
        <div className="feed-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'feed'}
            className={`feed-tab-btn ${tab === 'feed' ? 'active' : ''}`}
            onClick={() => setTab('feed')}
          >
            {t('Commentary')}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'qa'}
            className={`feed-tab-btn ${tab === 'qa' ? 'active' : ''}`}
            onClick={() => setTab('qa')}
          >
            {t('Questions')} {questions.length > 0 && <span className="feed-tab-badge">{questions.length}</span>}
          </button>
        </div>

        {speakingId && (
          <span className="on-air" aria-label={t('Speaking now')}>
            <span className="wave"><i /><i /><i /><i /></span> {t('On air')}
          </span>
        )}
      </div>

      {tab === 'qa' ? (
        <div className="feed-qa-view">
          {qaList.length === 0 ? (
            <p className="empty">{t('No questions asked yet. Ask Roy below!')}</p>
          ) : (
            <ol className="feed-qa-list">
              {qaList.map(({ question: q, answer }) => {
                const isSpeaking = answer && answer.id === speakingId
                return (
                  <li key={q.id} className={`feed-qa-item ${answer ? 'answered' : 'pending'}`}>
                    <div className="feed-qa-q">
                      <span className="qa-avatar you" aria-hidden="true">{t('You')}</span>
                      <div className="bubble">
                        <div className="who">
                          {t('You')} <span className="role">· {t('asked at {clock}', { clock: q.clock })}</span>
                          {!answer && <span className="qa-pill-pending">{t('Thinking...')}</span>}
                        </div>
                        <p>{q.text}</p>
                      </div>
                    </div>

                    {answer ? (
                      <div className="feed-qa-a" data-speaking={isSpeaking}>
                        <span className="qa-avatar roy" aria-hidden="true">{t.name('Roy')[0]}</span>
                        <div className="bubble">
                          <div className="who">
                            {t.name('Roy')} <span className="role">· {t('Answering you')}</span>
                            {isSpeaking && <span className="qa-on-air-pill">{t('On Air')}</span>}
                          </div>
                          <p>{answer.text}</p>
                        </div>
                      </div>
                    ) : (
                      <div className="feed-qa-waiting">
                        <span className="qa-spinner" aria-hidden="true" />
                        <span>{t('Roy is analyzing match data...')}</span>
                      </div>
                    )}
                  </li>
                )
              })}
            </ol>
          )}
        </div>
      ) : lines.length === 0 && pending.length === 0 ? (
        <p className="empty">{t('The commentators are ready. Kick off to hear them.')}</p>
      ) : (
        <ol>
          {pending.map((q) => (
            <li key={q.id} className="line viewer">
              <div className="bubble">
                <div className="who">{t('You')} <span className="role">· {t('asked at {clock}', { clock: q.clock })}</span></div>
                <p>{q.text}</p>
              </div>
            </li>
          ))}
          {lines.map((line) => {
            const voice = VOICES[line.speaker as keyof typeof VOICES] ?? VOICES.caller
            const question = line.reply_to ? byId.get(line.reply_to) : undefined
            return (
              <li key={line.id} className={`line ${line.speaker}`} data-excitement={line.excitement}
                data-speaking={line.id === speakingId}>
                <div className="bubble">
                  <div className="who">
                    {t.name(voice.name)} <span className="role">· {t(question ? 'Answering you' : voice.role)}</span>
                  </div>
                  {question && <blockquote>“{question.text}” <span>· {question.clock}</span></blockquote>}
                  <p>{line.text}</p>
                </div>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}
