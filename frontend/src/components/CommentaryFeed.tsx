import type { CommentaryLine, ViewerQuestion } from '../match/types'

const VOICES = {
  caller: { initial: 'G', name: 'Guy', role: 'Play-by-play' },
  analyst: { initial: 'S', name: 'Sonia', role: 'Analyst' },
} as const

/**
 * The commentary as a live feed: newest on top, the line being spoken highlighted.
 * Viewer questions show as "You" bubbles until Sonia answers; her answer quotes the question.
 */
export function CommentaryFeed({ lines, questions, speakingId }: {
  lines: CommentaryLine[]
  questions: ViewerQuestion[]
  speakingId: string | null
}) {
  const answered = new Set(lines.map((line) => line.reply_to).filter(Boolean))
  const pending = questions.filter((q) => !answered.has(q.id)).reverse()
  const byId = new Map(questions.map((q) => [q.id, q]))

  return (
    <section className="card feed" aria-label="Commentary" aria-live="polite">
      <h2>
        Commentary
        {speakingId && (
          <span className="on-air" aria-label="Speaking now">
            <span className="wave"><i /><i /><i /><i /></span> On air
          </span>
        )}
      </h2>
      {lines.length === 0 && pending.length === 0 ? (
        <p className="empty">The commentators are ready. Kick off to hear them.</p>
      ) : (
        <ol>
          {pending.map((q) => (
            <li key={q.id} className="line viewer">
              <span className="avatar" aria-hidden="true">You</span>
              <div className="bubble">
                <div className="who">You <span className="role">· asked at {q.clock}</span></div>
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
                <span className="avatar" aria-hidden="true">{voice.initial}</span>
                <div className="bubble">
                  <div className="who">
                    {voice.name} <span className="role">· {question ? 'Answering you' : voice.role}</span>
                    <span className="level-tag">{line.level}</span>
                    <span className="source" data-source={line.source}>{line.source === 'model' ? 'AI' : 'Auto'}</span>
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
