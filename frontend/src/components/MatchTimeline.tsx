import type { RankedEvent } from '../match/types'
import { BallIcon, CardIcon } from './Icons'

/** 0' to 90' (or 120' in extra time) with goals and cards marked: home above the line, away below. */
export function MatchTimeline({ events, homeTeam, minute }: { events: RankedEvent[]; homeTeam: string; minute: number }) {
  const extraTime = events.some(({ event }) => event.period >= 3)
  const end = extraTime ? 120 : 90
  const marks = events
    .filter(({ event, moment }) => event.period < 5 && (moment.kind === 'goal' || moment.kind === 'card'))
    .map(({ event, moment }) => ({
      id: event.id,
      home: event.team === homeTeam,
      at: Math.min(100, (event.minute / end) * 100),
      goal: moment.kind === 'goal',
      red: /red|second/i.test(event.card ?? event.foul?.card ?? ''),
      label: `${event.minute}' ${moment.kind === 'goal' ? 'Goal' : 'Card'}: ${event.player ?? event.team}`,
    }))
  const now = Math.min(100, (minute / end) * 100)

  return (
    <div className="timeline" aria-label="Match timeline">
      <div className="timeline-track">
        <span className="timeline-progress" style={{ width: `${now}%` }} />
        {[0, 45, 90, ...(extraTime ? [105, 120] : [])].map((m) => (
          <span key={m} className="tick" style={{ left: `${(m / end) * 100}%` }}>{m}'</span>
        ))}
        {marks.map((m) => (
          <span key={m.id} className={`mark ${m.home ? 'home' : 'away'}`} style={{ left: `${m.at}%` }} title={m.label}>
            {m.goal ? <BallIcon size={14} /> : <CardIcon size={14} color={m.red ? 'red' : 'yellow'} />}
          </span>
        ))}
        <span className="now" style={{ left: `${now}%` }} aria-label={`${minute} minutes`} />
      </div>
    </div>
  )
}
