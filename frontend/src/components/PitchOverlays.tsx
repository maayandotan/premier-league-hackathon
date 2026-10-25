import type { CommentaryLine, RankedEvent } from '../match/types'
import { teamCode } from '../match/teams'

const surname = (name?: string) => name?.split(' ').slice(-1)[0] ?? ''

/** A TV goal graphic that sweeps across the pitch once per goal (keyed by the goal's id). */
export function GoalBanner({ events, score }: { events: RankedEvent[]; score: string }) {
  const goal = events.slice(0, 8).find(({ event, moment }) => moment.kind === 'goal' && event.period < 5)
  if (!goal) return null
  const { event, moment } = goal
  return (
    <div key={event.id} className="goal-banner" role="status" aria-live="assertive">
      <span className="goal-word">Goal</span>
      <span className="goal-detail">
        <strong>{surname(event.player)}</strong> {event.minute}' · {teamCode(event.team)} · {score}
      </span>
      <span className="goal-reason">{moment.reason}</span>
    </div>
  )
}

const VOICE_NAMES: Record<string, string> = { caller: 'Davis · Play-by-play', analyst: 'Roy · Analyst' }

/** Live subtitles: the line being spoken right now, as a broadcast lower third. */
export function LowerThird({ lines, speakingId }: { lines: CommentaryLine[]; speakingId: string | null }) {
  const line = speakingId ? lines.find((l) => l.id === speakingId) : undefined
  if (!line) return null
  return (
    <div key={line.id} className={`lower-third ${line.speaker}`} aria-hidden="true">
      <span className="lt-name">{line.reply_to ? 'Roy · Answering you' : VOICE_NAMES[line.speaker] ?? line.speaker}</span>
      <span className="lt-text">{line.text}</span>
    </div>
  )
}
