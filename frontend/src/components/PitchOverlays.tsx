import type { CommentaryLine, RankedEvent } from '../match/types'
import { teamCode } from '../match/teams'
import { useT } from '../i18n'

const surname = (name?: string) => name?.split(' ').slice(-1)[0] ?? ''

/** A TV goal graphic that sweeps across the pitch once per goal (keyed by the goal's id). */
export function GoalBanner({ events, score }: { events: RankedEvent[]; score: string }) {
  const t = useT()
  const goal = events.slice(0, 8).find(({ event, moment }) => moment.kind === 'goal' && event.period < 5)
  if (!goal) return null
  const { event, moment } = goal
  return (
    <div key={event.id} className="goal-banner" role="status" aria-live="assertive">
      <span className="goal-word">{t('Goal')}</span>
      <span className="goal-detail">
        <strong>{surname(event.player)}</strong> {event.minute}' · {teamCode(event.team)} · {score}
      </span>
      <span className="goal-reason">{t.reason(moment.reason)}</span>
    </div>
  )
}

const VOICE_NAMES: Record<string, [string, string]> = { caller: ['Davis', 'Play-by-play'], analyst: ['Roy', 'Analyst'] }

/** Live subtitles: the line being spoken right now, as a broadcast lower third. */
export function LowerThird({ lines, speakingId }: { lines: CommentaryLine[]; speakingId: string | null }) {
  const t = useT()
  const line = speakingId ? lines.find((l) => l.id === speakingId) : undefined
  if (!line || line.reply_to) return null // an answer shows in the answer card instead
  return (
    <div key={line.id} className={`lower-third ${line.speaker}`} aria-hidden="true">
      <span className="lt-name">{line.reply_to ? `${t.voice('Roy')} · ${t('Answering you')}`
        : VOICE_NAMES[line.speaker] ? `${t.voice(VOICE_NAMES[line.speaker][0])} · ${t(VOICE_NAMES[line.speaker][1])}`
        : line.speaker}</span>
      <span className="lt-text">{line.text}</span>
    </div>
  )
}
