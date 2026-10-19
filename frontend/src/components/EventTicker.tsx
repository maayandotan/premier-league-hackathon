import type { ReactNode } from 'react'
import type { MatchEvent, Moment, RankedEvent } from '../match/types'
import { BallIcon, CardIcon, ClockIcon, FlagIcon, SwapIcon, TargetIcon, WhistleIcon } from './Icons'

function icon(e: MatchEvent, m: Moment): ReactNode {
  if (m.kind === 'goal') return <BallIcon />
  const card = e.card ?? e.foul?.card
  if (card) return <CardIcon color={/red|second/i.test(card) ? 'red' : 'yellow'} />
  if (e.type === 'Shot') return <TargetIcon />
  if (e.type === 'Offside' || m.reason.includes('corner')) return <FlagIcon />
  if (e.type === 'Substitution') return <SwapIcon />
  if (e.type === 'Foul Committed') return <WhistleIcon />
  if (e.type === 'Half Start' || e.type === 'Half End') return <ClockIcon />
  return <span className="dot" />
}

/** Key moments only (what the Moment Ranker scored 3+), with the reason it mattered. */
export function EventTicker({ events, homeTeam }: { events: RankedEvent[]; homeTeam: string }) {
  const key = events.filter(({ moment }) => moment.score >= 3).slice(0, 12)
  return (
    <section className="card ticker" aria-label="Key moments">
      <h2>Key moments</h2>
      {key.length === 0 ? (
        <p className="empty">Nothing notable yet.</p>
      ) : (
        <ol>
          {key.map(({ event: e, moment }) => (
            <li key={e.id} className={e.team === homeTeam ? 'home' : 'away'}
              data-level={moment.score >= 9 ? 'high' : moment.score >= 6 ? 'mid' : 'low'}>
              <span className="minute">{e.minute}'</span>
              <span className="icon" aria-hidden="true">{icon(e, moment)}</span>
              <span className="what">
                <strong>{e.player?.split(' ').slice(-1)[0] ?? e.team}</strong>
                <span className="reason">{moment.reason}</span>
              </span>
              <span className="score-badge" title="How interesting the ranker found it">{moment.score}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
