import type { CommentaryLine } from '../match/types'

const VOICES = {
  caller: { initial: '🎙️', name: 'Guy', role: 'Play-by-play' },
  analyst: { initial: '🧠', name: 'Sonia', role: 'Analyst' },
} as const

/** The commentary as a live feed: newest on top, the line being spoken highlighted. */
export function CommentaryFeed({ lines, speakingId }: { lines: CommentaryLine[]; speakingId: string | null }) {
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
      {lines.length === 0 ? (
        <p className="empty">The commentators are ready. Kick off to hear them.</p>
      ) : (
        <ol>
          {lines.map((line) => {
            const voice = VOICES[line.speaker as keyof typeof VOICES] ?? VOICES.caller
            return (
              <li key={line.id} className={`line ${line.speaker}`} data-excitement={line.excitement}
                data-speaking={line.id === speakingId}>
                <span className="avatar" aria-hidden="true">{voice.initial}</span>
                <div className="bubble">
                  <div className="who">
                    {voice.name} <span className="role">· {voice.role}</span>
                    <span className="source" data-source={line.source}>{line.source === 'model' ? 'AI' : 'Auto'}</span>
                  </div>
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
